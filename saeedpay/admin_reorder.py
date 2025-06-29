ADMIN_REORDER = (
    {
        'app': 'customers',
        'label': 'Customers',
        'models': (
            'customers.Customer',
        )
    },
    {
        'app': 'cas_auth',
        'label': 'API',
        'models': (
            'cas_auth.APILog',
            'cas_auth.Token'
        )
    },
)
