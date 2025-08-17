from django.contrib import admin

from credit.models import CreditLimit, Statement
from credit.admin.credit_limit import CreditLimitAdmin
from credit.admin.statement import StatementAdmin

admin.site.register(CreditLimit, CreditLimitAdmin)
admin.site.register(Statement, StatementAdmin)
