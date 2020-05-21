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


LIST_TICKETS = 'list_tickets'
INITIATE_PURCHASE = 'purchase_ticket'
CONFIRM_PURCHASE = 'confirm_purchase.yes'
TICKET_UNAVAILABLE_RETRY = 'ticket_unavailable.retry'
PHONE_NUMBER_REGEX = r'\+[0-9]{6,15}'  # determines which phone numbers are eligible to buy lottery


logger = logging.getLogger('testlogger')  # this is the logger defined by django-heroku


@api_view(['POST'])
def webhook(request):
    """ This method handles HTTP requests for the Dialogflow webhook """
    try:
        action = request.data.get('queryResult').get('action')
    except AttributeError:
        logger.error('AttributeError encountered when trying to extract action from request')
        return Response('Action not found in the request', status=status.HTTP_400_BAD_REQUEST)
    phone_number = get_phone_number(request)
    if action == LIST_TICKETS:
        return list_tickets(phone_number)
    if action == INITIATE_PURCHASE:
        return initiate_purchase(request)
    if action == CONFIRM_PURCHASE:
        return confirm_purchase(request)
    if action == TICKET_UNAVAILABLE_RETRY:
        return ticket_unavailable_retry(request)
    logger.error('Dialogflow action "%s" not recognized', action)
    return Response(f'Action "{action}" not recognized', status=status.HTTP_400_BAD_REQUEST)


def list_tickets(phone_number):
    """ List a user's tickets """
    tickets = Ticket.objects.filter(phone_number=phone_number)
    if tickets.exists():
        message = ""
        for t in tickets:
            if t.contest.is_active:
                message += f'    🎟 Serie {t.number} para {t.contest}\n'
        if message:
            message.strip()
            return text_response('Tenes los siguientes numeros:\n' + message)
    return text_response('Todavía no has comprado tiquetes para los próximos sorteos.')


def initiate_purchase(request):
    """ Initiates the ticket purchase flow, validating the parameters provided by the user. If any
    problems are found with the parameters a non-empty error_response will be reutrned to prompt the
    user for correction. The method also returns a dictionary holding the validated parameters.
    """
    # validate phone number
    if (phone_number := get_phone_number(request)) is None:
        return text_response('Lo sentimos pero tu número de celular no califica para hacer compras'
                             'de lotería.')

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
                message += f'    • {c}: por un premio de ₡{c.prize_pool}\n'
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
            if cache_hit is not None and cache_hit != phone_number:
                return text_response('Desafortunadamente, el tiquete que querés está reservado '
                                     'por otro usuario. Intentá de nuevo en 15 mins. para ver si '
                                     'se liberó.')
        else:
            return event_trigger_response('ticket_unavailable', {'contest': contest_id})
    else:
        return text_response(f'¿Qué número te gustaría comprar? En este sorteo los números tienen '
                             f'el siguiente formato {contest.example_number}, y cuestan '
                             f'₡{contest.price_per_ticket} cada uno')

    # All parameters are validated
    # reserve number on cache
    cache.set(get_cache_key(ticket_number, contest), phone_number,
              timeout=settings.RESERVATION_THRESHOLD)

    params = {
        "phone_number": phone_number,  # may not need it
        "contest": contest_id,
        "contest-name": contest.name,
        "price": contest.price_per_ticket,
        "ticket_number": ticket_number,
    }
    return event_trigger_response('confirm_purchase', params)


def ticket_unavailable_retry(request):
    """ Responds to a retry if the first number tried by the user was unavailable """
    # TODO cut out repeated code
    params = request.data['queryResult']['parameters']
    phone_number = get_phone_number(request)
    contest_id = params['contest']
    contest = Contest.objects.get_active_contests().get(id=contest_id)
    ticket_number = params.get('ticket_number')
    if ticket_number:
        try:
            ticket_available = contest.number_is_available(ticket_number)
        except ValueError:
            return text_response(f'El número no está en el formato correcto. Escribí el número que'
                                 f'querés en este formato: {contest.example_number}')
        if ticket_available:
            # reserved by another user
            cache_hit = cache.get(get_cache_key(ticket_number, contest))
            if cache_hit is not None and cache_hit != phone_number:
                return text_response('Desafortunadamente, el tiquete que querés está reservado '
                                     'por otro usuario. Intentá de nuevo en 15 mins. para ver si '
                                     'se liberó.')
        else:
            return event_trigger_response('ticket_unavailable', {'contest': contest.id})
    else:
        return text_response(f'¿Qué número te gustaría comprar? En este sorteo los números tienen '
                             f'el siguiente formato {contest.example_number}, y cuestan '
                             f'₡{contest.price_per_ticket} cada uno')

    # All parameters are validated
    # reserve number on cache
    cache.set(get_cache_key(ticket_number, contest), phone_number,
              timeout=settings.RESERVATION_THRESHOLD)

    params = {
        "phone_number": phone_number,  # may not need it
        "contest": contest.id,
        "contest-name": contest.name,
        "price": contest.price_per_ticket,
        "ticket_number": ticket_number,
    }
    return event_trigger_response('confirm_purchase', params)

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
        return text_response('Desafortunadamente, el tiquete que querés ya no está disponible 😢')
    # check the cache
    cache_hit = cache.get(get_cache_key(ticket_number, contest))
    if  cache_hit is not None and cache_hit != phone_number:
        return text_response('Desafortunadamente, el tiquete que querés está reservado '
                             'por otro usuario. Intentá de nuevo en 15 mins. para ver si se '
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
            logger.critical('Failed to create ticket %s (contest %s) for user %s who already paid',
                             ticket_number, str(contest), phone_number)
            # TODO add slack notif
            return text_response('Hubo un error reservando tu numero. Estamos investigandolo y te'\
                                 ' contactaermos pronto.')
        message = f'Listo! Tu compra del compra del numero "{ticket_number}" para el sorteo '\
                  f'{contest}" fue exitosa. Buena suerte! 🍀'
    else:  # TODO identify failure reason and notify slack if it was a system issue
        logger.info('Payment failed for phone number %s', phone_number)
        message = 'Desafortunadamente, hubo un problema procesando el pago. Por favor intenta más'\
                  'tarde.'
    return text_response(message)


# utility functions

def get_phone_number(request):
    """ Extracts and validates the user's phone number from the request """
    string = request.data['originalDetectIntentRequest']['payload']['data']['From']
    if match := re.search(PHONE_NUMBER_REGEX, string):
        return match.group()


def text_response(text: str) -> Response:
    """ Wraps a message in a Response object with the appropriate format """
    data = {
        'fulfillmentText': text
    }
    return Response(data=data, status=status.HTTP_200_OK)


def event_trigger_response(event: str, params: dict) -> Response:
    return Response(data={
        # trigger confirmation intent
        "followupEventInput": {
            "name": event,
            "languageCode": "es",
            # this info will be used to prompt user for confirmation
            "parameters": params
        }
    }, status=status.HTTP_200_OK)


def get_cache_key(ticket_number: str, contest: Contest) -> str:
    """ Gives a unique string to identify a ticket in the cache """
    return f'{contest.id}--{ticket_number}'
