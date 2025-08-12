ADMIN_REORDER = (
    {
        "app": "customers",
        "label": "کاربران",
        "models": (
            "cas_auth.User",
            'customers.Customer',
            'merchants.Merchant',
            'profiles.Profile',
        ),
    },
    {
        "app": "store",
        "label": "فروشگاه‌ها",
        "models": (
            "store.Store",
            "store.StoreContract",
            "store.StoreApiKey",
        ),
    },
    {
        "app": "tickets",
        "label": "تیکت‌ها",
        "models": (
            "tickets.Ticket",
            "tickets.TicketMessage",
            "tickets.TicketCategory",
        ),
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
