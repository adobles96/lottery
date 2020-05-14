""" Handles fulfillment and slot-filling webhooks coming from Dialogflow """

from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import JSONParser
from rest_framework.response import Response

from core.models import Ticket

# Intents
SEE_TICKETS = 'See tickets'

# utility functions

def get_phone_number(request):
    session = request.data["session"]
    return session.split('/')[-1]  # this extracts the session id, which is the phone number

def make_response(text):
    data = {
        'fulfillmentText': text
    }
    return Response(data=data)


@api_view(['POST']) # @parser_classes([JSONParser])
def webhook(request):
    """ This method handles HTTP requests for the Dialogflow webhook """ 
    intent = request.data.get('queryResult').get('intent')
    if intent['displayName'] == SEE_TICKETS:
        phone_number = get_phone_number(request)
        return make_response(text=see_tickets(phone_number))

def see_tickets(phone_number):
    tickets = Ticket.objects.filter(phone_number=phone_number)
    if tickets.exists():
        message = ""
        for t in tickets:
            if t.contest.is_active:
                message += f"🎟 Serie {t.number} para {t.contest.name} (sorteo del {t.contest.draw_date})\n"
        if message:
            message.strip()
            return "Tenes los siguientes numeros: \n" + message
    return "Todavía no has comprado tiquetes para los siguientes sorteos."
