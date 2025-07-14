# wallets/utils/reference.py
import datetime
import random


def generate_reference_code(prefix="PR", random_digits=6):
    now = datetime.datetime.now()
    date_part = now.strftime("%y%m%d")
    rand_part = str(
        random.randint(10 ** (random_digits - 1), 10 ** random_digits - 1)
    )
    return f"{prefix}{date_part}{rand_part}"
