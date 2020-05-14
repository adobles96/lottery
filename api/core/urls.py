from django.urls import path

from core.views.dialogflow.webhook import webhook

urlpatterns = [
    path('dialogflow/webhook', webhook, name='dialogflow-webhook'),
]
