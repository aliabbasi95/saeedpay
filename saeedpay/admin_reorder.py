ADMIN_REORDER = (
    {
        "app": "customers",
        "label": "کاربران",
        "models": (
            "cas_auth.User",
            "customers.Customer",
            "merchants.Merchant",
            "profiles.Profile",
            "profiles.ProfileKYCAttempt",
        ),
    },
    {
        "app": "contact",
        "label": "فرم تماس",
        "models": (
            "contact.Contact",
        ),
    },
    {
        "app": "store",
        "label": "فروشگاه‌ها",
        "models": (
            "store.Store",
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
        "app": "banking",
        "label": "بانک",
        "models": (
            "banking.Bank",
            "banking.BankCard",
        ),
    },
    {
        "app": "blogs",
        "label": "بلاگ",
        "models": (
            "blogs.Article",
            "blogs.ArticleImage",
            "blogs.Tag",
            "blogs.Comment",
        ),
    },
    {
        "app": "credit",
        "label": "اعتباری",
        "models": (
            "credit.CreditLimit",
            "credit.Statement",
            "credit.StatementLine",
        ),
    },
    {
        "app": "wallets",
        "label": "کیف پول",
        "models": (
            "wallets.Wallet",
            "wallets.Transaction",
            "wallets.PaymentRequest",
            "wallets.WalletTransferRequest",
            "wallets.Installment",
            "wallets.InstallmentPlan",
        ),
    },
    {
        "app": "cas_auth",
        "label": "API",
        "models": (
            "cas_auth.APILog",
            "cas_auth.Token",
        ),
    },
)
