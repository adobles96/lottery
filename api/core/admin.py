""" Admin site customization """

from django.contrib import admin

from core import models


class ContestAdmin(admin.ModelAdmin):
    """ ModelAdmin for Contest model """
    list_display = ('name', 'draw_date', 'is_active', 'num_tickets_sold')
    fields = ('name', 'draw_date', 'prize_pool', 'price_per_ticket', 'example_number', 'regex')
    readonly_fields = ('regex',)
    date_hierarchy = 'draw_date'


class TicketAdmin(admin.ModelAdmin):
    """ ModelAdmin for Ticket model """
    list_display = ('contest', 'number', 'phone_number')
    readonly_fields = ('number', 'phone_number', 'contest', 'purchase_date')
    date_hierarchy = 'purchase_date'
    list_filter = ['contest']
    search_fields = ['number', 'phone_number']


admin.site.register(models.Contest, ContestAdmin)
admin.site.register(models.Ticket, TicketAdmin)
