""" Handles fulfillment and slot-filling webhooks coming from Dialogflow """

import logging
import re

from django.conf import settings
from django.core.cache import cache
from django.db.utils import IntegrityError
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from core.models import Ticket, Contest

# Actions
LIST_TICKETS = 'list_tickets'
INITIATE_PURCHASE = 'purchase_ticket'
CONFIRM_PURCHASE = 'confirm_purchase.yes'


@api_view(['POST'])
def webhook(request):
    """ This method handles HTTP requests for the Dialogflow webhook """
    try:
        action = request.data.get('queryResult').get('action')
    except AttributeError:
        logging.error('AttributeError encountered when trying to extract action from request')
        return Response('Action not found in the request', status=status.HTTP_400_BAD_REQUEST)
    phone_number = get_phone_number(request)
    if action == LIST_TICKETS:
        return list_tickets(phone_number)
    if action == INITIATE_PURCHASE:
        return initiate_purchase(request)
    if action == CONFIRM_PURCHASE:
        return confirm_purchase(request)
    logging.error('Dialogflow action "%s" not recognized', action)
    return Response(f'Action "{action}" not recognized', status=status.HTTP_400_BAD_REQUEST)


def list_tickets(phone_number):
    """ List a user's tickets """
    tickets = Ticket.objects.filter(phone_number=phone_number)
    if tickets.exists():
        message = ""
        for t in tickets:
            if t.contest.is_active:
                message += f"    🎟 Serie {t.number} para {t.contest}\n"
        if message:
            message.strip()
            return text_response("Tenes los siguientes numeros:\n" + message)
    return text_response("Todavía no has comprado tiquetes para los siguientes sorteos.")


def initiate_purchase(request):
    """ Initiates the ticket purchase flow, validating the parameters provided by the user. If any
    problems are found with the parameters a non-empty error_response will be reutrned to prompt the
    user for correction. The method also returns a dictionary holding the validated parameters.
    """
    # validate phone number
    phone_number = get_phone_number(request)
    if not validate_phone_number(phone_number):
        return text_response('Lo sentimos pero tu número de celular no califica para hacer compras \
            de lotería.')

    params = request.data['queryResult']['parameters']

    # validate contest
    contest_id = params['contest']
    if contest_id:
        try:
            contest = Contest.objects.get_active_contests().get(id=contest_id)
        except Contest.DoesNotExist:
            return text_response('Error: El sorteo que querés jugar no está disponible.')
    else:
        contests = Contest.objects.get_active_contests()
        if contests.exists():
            message = 'En cual sorteo estás interesado? Las opciones son:\n'
            for c in Contest.objects.get_active_contests():
                message += f'    • {c}: por un premio de ₡{c.prize_pool}'
            return text_response(message)
        else:
            return text_response('Desafortunadamente, no hay sorteos disponibles en este momento.')

    # validate ticket number
    ticket_number = params['ticket_number']
    if ticket_number:
        try:
            ticket_available = contest.number_is_available(ticket_number)
        except ValueError:
            return text_response(f'El número no está en el formato correcto. Escribí el número que'
                                 f'querés en este formato: {contest.example_number}')
        if ticket_available:
            # reserved by another user
            cache_hit = cache.get(get_cache_key(ticket_number, contest))
            if  cache_hit is not None and cache_hit != phone_number:
                return text_response('Desafortunadamente, el tiquete que querés está reservado'
                                     'por otro usuario. Intentá de nuevo en 15 mins. para ver si se'
                                     'liberó.')
        else:
            return text_response('Desafortunadamente, el tiquete que querés no está disponible 😢')
    else:
        return text_response(f'¿Qué número te gustaría comprar? En este sorteo los números tienen'
                             f'el siguiente formato {contest.example_number}, y cuestan '
                             f'₡{contest.price_per_ticket} cada uno')

    # All parameters are validated
    # reserve number on cache
    cache.set(get_cache_key(ticket_number, contest), phone_number,
              timeout=settings.RESERVATION_THRESHOLD)
    # prompt user for confirmation & trigger confirmation event
    message = f'¿Deseas confirmar la compra del numero "{ticket_number}" por '\
              f'₡{contest.price_per_ticket} para el sorteo "{contest}"? Te lo cobraríamos a tu '\
              f'cuenta de celular.'
    return Response(data={
        "fulfillmentText": message,
        "followupEventInput": {
            "name": "confirm_purchase",
            "languageCode": "es",
            "parameters": {
                "phone_number": phone_number,  # may not need it
                "contest": contest_id,
                "ticket_number": ticket_number,
            }
        }
    }, status=status.HTTP_200_OK)


def confirm_purchase(request):
    """ Confirms purchase of a ticket """
    params = request.data['queryResult']['parameters']
    contest = Contest.objects.get_active_contests().get(id=params['contest'])
    ticket_number = params['ticket_number']
    phone_number = get_phone_number(request)

    # redundancy check that ticket is avaiable
    try:
        ticket_available = contest.number_is_available(ticket_number)
    except ValueError:
        return text_response(f'El número no está en el formato correcto. Escribí el número que'
                            f'querés en este formato: {contest.example_number}')
    if not ticket_available:
        return text_response('Desafortunadamente, el tiquete que querés no está disponible 😢')
    # check the cache
    cache_hit = cache.get(get_cache_key(ticket_number, contest))
    if  cache_hit is not None and cache_hit != phone_number:
        return text_response('Desafortunadamente, el tiquete que querés está reservado'
                             'por otro usuario. Intentá de nuevo en 15 mins. para ver si se'
                             'liberó.')
    # set cache again in case the reservation had expired
    cache.set(get_cache_key(ticket_number, contest), phone_number,
              timeout=settings.RESERVATION_THRESHOLD)

    # process payment
    print(f'SIMULATING CALL TO PAYMENT API. CHARGING ₡{contest.price_per_ticket} TO'
          f'{phone_number}')
    payment_succeded = True  # simulating success of payment
    if payment_succeded:
        try:
            Ticket.objects.create(contest=contest, number=ticket_number, phone_number=phone_number)
        except IntegrityError:
            logging.critical('Failed to create ticket %s (contest %s) for user %s who already paid',
                             ticket_number, str(contest), phone_number)
            # TODO add slack notif
            return text_response('Hubo un error reservando tu numero. Estamos investigandolo y te'\
                                 ' contactaermos pronto.')
        message = f'Listo! Tu compra del compra del numero "{ticket_number}" para el sorteo '\
                  f'{contest}" fue exitosa. Buena suerte! 🍀'
    else:  # TODO identify failure reason and notify slack if it was a system issue
        logging.info('Payment failed for phone number %s', phone_number)
        message = 'Desafortunadamente, hubo un problema procesando el pago. Por favor intenta más'\
                  'tarde.'
    return text_response(message)


# utility functions

def get_phone_number(request):
    """ Extracts the user's phone number from the dialogflow session id """
    session = request.data["session"]
    return session.split('/')[-1]  # this extracts the session id, which is the phone number


def validate_phone_number(phone_number):
    """ Validates that the user's phone number is valid (ie that it is a Costa Rican phone number)
    """
    if re.match(r'\+506([0-9]{8})', phone_number):
        return True
    return False


def text_response(text):
    """ Wraps a message in a Response object with the appropriate format """
    data = {
        'fulfillmentText': text
    }
    return Response(data=data, status=status.HTTP_200_OK)


def get_cache_key(ticket_number, contest):
    """ Gives a unique string to identify a ticket in the cache """
    return f'{contest.id}--{ticket_number}'
