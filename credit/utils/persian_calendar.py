# credit/utils/persian_calendar.py

"""
Utility functions for Persian (Jalali) calendar operations
"""

from datetime import timedelta

from persiantools.jdatetime import JalaliDate


def is_last_day_of_persian_month(date=None) -> bool:
    """
    Check if the given date is the last day of the Persian month
    """
    if date is None:
        date = JalaliDate.today()

    next_day = date + timedelta(days=1)
    return next_day.month != date.month


def get_persian_month_days(year: int, month: int) -> int:
    """
    Get number of days in a Persian month
    """
    if month < 1 or month > 12:
        return 0

    # Persian calendar months: 31 days for months 1-6, 30 for 7-11, 29/30 for 12
    if month <= 6:
        return 31
    elif month <= 11:
        return 30
    else:  # month == 12
        # Check if it's a leap year
        from persiantools.jdatetime import JalaliDate
        test_date = JalaliDate(year, 12, 30)
        return 30 if test_date.month == 12 else 29


def get_next_persian_month_start() -> JalaliDate:
    """
    Get the first day of the next Persian month
    """
    today = JalaliDate.today()
    next_day = today + timedelta(days=1)

    if next_day.month != today.month:
        return next_day
    else:
        # Find last day of current month
        current_month = today.month
        current_year = today.year

        # Add days until month changes
        test_date = today
        while test_date.month == current_month:
            test_date += timedelta(days=1)

        return test_date


def get_business_days_until_month_end() -> int:
    """
    Get number of business days until end of Persian month
    """
    today = JalaliDate.today()
    days_until_end = 0

    current = today
    while current.month == today.month:
        # Persian week: Saturday (0) to Friday (6)
        # Business days are Saturday to Wednesday (0-4)
        if current.weekday() <= 4:  # 0-4 are business days
            days_until_end += 1
        current += timedelta(days=1)

    return days_until_end


def get_days_until_month_end() -> int:
    """
    Get total days until end of Persian month
    """
    today = JalaliDate.today()
    days_until_end = 0

    current = today
    while current.month == today.month:
        days_until_end += 1
        current += timedelta(days=1)

    return days_until_end


def get_month_name(month: int) -> str:
    """
    Get Persian month name
    """
    month_names = {
        1: 'فروردین',
        2: 'اردیبهشت',
        3: 'خرداد',
        4: 'تیر',
        5: 'مرداد',
        6: 'شهریور',
        7: 'مهر',
        8: 'آبان',
        9: 'آذر',
        10: 'دی',
        11: 'بهمن',
        12: 'اسفند'
    }
    return month_names.get(month, 'نامعلوم')


def format_persian_date(date: JalaliDate) -> str:
    """
    Format Persian date as string
    """
    return f"{date.year:04d}/{date.month:02d}/{date.day:02d}"


def get_current_persian_month_info() -> dict:
    """
    Get current Persian month information
    """
    today = JalaliDate.today()

    return {
        'year': today.year,
        'month': today.month,
        'month_name': get_month_name(today.month),
        'day': today.day,
        'is_last_day': is_last_day_of_persian_month(),
        'days_in_month': get_persian_month_days(today.year, today.month),
        'days_until_end': get_days_until_month_end(),
        'business_days_until_end': get_business_days_until_month_end()
    }
