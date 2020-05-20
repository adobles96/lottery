""" Defines a command to update Dialogflow entities for contests and ticket numbers """

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
import dialogflow

from core.models import Contest


CONTEST_ENTITY_TYPE = 'contest-name'
TICKET_NUMBER_ENTITY_TYPE = 'ticket-number'


class Command(BaseCommand):
    help = 'Updates Dialogflow contest & ticket_number entities to the currently active ones'

    def handle(self, *args, **options):
        if os.environ.get('GOOGLE_APPLICATION_CREDENTIALS') is None:
            raise CommandError('The environment variable "GOOGLE_APPLICATION_CREDENTIALS" is not '
                               'set. Could not authenticate.')
        client = dialogflow.EntityTypesClient()
        contest_type, ticket_type = get_entity_types(client, settings.DIALOGFLOW_PROJECT_ID)
        current_contests = [c.value for c in contest_type.entities]
        current_tickets = [t.value for t in ticket_type.entities]
        contests_to_create, contests_to_delete = [], current_contests.copy()
        tickets_to_create, tickets_to_delete = [], current_tickets.copy()

        # Compute entities to create & delete
        for c in Contest.objects.get_active_contests():
            if str(c.id) in current_contests:
                # entity already exists, don't delete it
                contests_to_delete.remove(str(c.id))
            else:
                # new entity
                contests_to_create.append({"value": str(c.id), "synonyms": [c.name]})
            if c.regex in current_tickets:
                # entity already exists, don't delete it
                tickets_to_delete.remove(c.regex)
            else:
                # new entity
                tickets_to_create.append({"value": c.regex})

        if not (contests_to_create or contests_to_delete or tickets_to_create or tickets_to_delete):
            self.stdout.write(self.style.SUCCESS('All entities up to date. No changes made.'))
        else:
            # Create new entities
            if contests_to_create:
                client.batch_create_entities(contest_type.name, contests_to_create)
                self.stdout.write('Created the following contests:\n')
                for c in contests_to_create:
                    self.stdout.write(f'    - {c["value"]}\n')
            if tickets_to_create:
                client.batch_create_entities(ticket_type.name, tickets_to_create)
                self.stdout.write('Created the following tickets:\n')
                for t in tickets_to_create:
                    self.stdout.write(f'    - {t["value"]}\n')

            # Delete outdated entities
            if contests_to_delete:
                client.batch_delete_entities(contest_type.name, contests_to_delete)
                self.stdout.write('Deleted the following contests:\n')
                for c in contests_to_delete:
                    self.stdout.write(f'    - {c}\n')
            if tickets_to_delete:
                client.batch_delete_entities(ticket_type.name, tickets_to_delete)
                self.stdout.write('Deleted the following tickets:\n')
                for t in tickets_to_delete:
                    self.stdout.write(f'    - {t}\n')

            self.stdout.write(self.style.SUCCESS('Entities updated successfully'))


def get_entity_types(client: dialogflow.EntityTypesClient, project_id: str):
    """ Returns a tuple of EntityType objects (protobuf objects) corresponding to the contest and
    ticket entity types
    """
    name = client.project_agent_path(project_id)
    response = client.list_entity_types(name)
    contest_type = None
    ticket_type = None
    for entity_type in response:
        if entity_type.display_name == CONTEST_ENTITY_TYPE:
            contest_type = entity_type
        elif entity_type.display_name == TICKET_NUMBER_ENTITY_TYPE:
            ticket_type = entity_type
    if contest_type is None:
        raise RuntimeError('Contest entity type not found in dialogflow project. Did you change '\
                           'the entity display name?')
    if ticket_type is None:
        raise RuntimeError('Ticket entity type not found in dialogflow project. Did you change '\
                           'the entity display name?')
    return contest_type, ticket_type
