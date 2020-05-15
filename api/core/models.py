""" Defines core models """

import re
import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone
from phonenumber_field.modelfields import PhoneNumberField


class ContestManager(models.Manager):
    """ Manager for Contest model """
    # Possibly add order_by in meta class

    def get_active_contests(self):
        """ Retrieves active contests (ie contests that are still selling tickets). More efficient
        than calling Contest.objects.filter(is_active=True).
        """
        cutoff = timezone.now() + datetime.timedelta(hours=settings.HOURS_TRESHOLD)
        return self.filter(draw_date__gt=cutoff)


class Contest(models.Model):
    """ Models a single lottery contest """
    name = models.CharField(max_length=255)
    draw_date = models.DateTimeField()
    prize_pool = models.IntegerField()  # in colones
    regex = models.CharField(max_length=255)
    example_number = models.CharField(max_length=255)  # an example of a valid ticket number

    @property
    def is_active(self):
        """ Whether the contest is active (ie hasn't been drawn yet) """
        cutoff = timezone.now() + datetime.timedelta(hours=settings.HOURS_THRESHOLD)
        return self.draw_date > cutoff

    def number_is_available(self, number: str) -> bool:
        """ Checks if the provided number is available for purchase

        Args:
            number (str): The lottery number to check

        Returns:
            bool: True if the number is both a valid ticket number and is avaialble, or False if it
                is a valid ticket number but is not available

        Raises:
            ValueError: if the provided number is not a valid ticket number
        """
        if not re.match(self.regex, number):
            raise ValueError('number is not a valid ticket number for this contest')
        if self.tickets_sold.filter(number=number).exists():
            return False
        return True


class Ticket(models.Model):
    """ Represents a ticket that has been sold/purchased """
    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name='tickets_sold')
    number = models.CharField(max_length=255)  # remember to validate at the serializer level
    phone_number = PhoneNumberField()
    purchase_date = models.DateField(auto_now_add=True)

    def validate_number(self) -> bool:
        """ Returns True if the ticket number matches the number format of the contest """
        if re.match(self.contest.regex, self.number):
            return True
        return False

# class WinningNumber(models.Model):
#    contest = models.ForeignKey(Contest, on_delete=models.CASCADE, related_name='winning_numbers')