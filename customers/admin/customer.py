# customers/admin/customer.py
from django.contrib import admin

from customers.models import Customer
from lib.erp_base.admin import BaseAdmin


@admin.register(Customer)
class CustomerAdmin(BaseAdmin):
    pass
