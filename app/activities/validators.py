from django.core.exceptions import ValidationError

VALID_UNITS = ["kg", "g", "l", "ml", "lb", "oz"]


def validate_unit_measurement(value: str):
    """Validate that the given value is a recognized unit of measurement."""
    if value.lower().strip() not in VALID_UNITS:
        raise ValidationError(
            f"'{value}' n'est pas une unité de mesure valide. "
            f"Unités acceptées : {', '.join(VALID_UNITS)}"
        )
