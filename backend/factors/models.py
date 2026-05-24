from django.db import models


class EmissionFactor(models.Model):
    """
    Versioned lookup table for GHG conversion factors.
    Historical records are never retroactively changed when a new factor version is published.
    Primary source: DEFRA 2024. Supplemented by EPA eGRID 2023 for US electricity.
    """
    # e.g. "DEFRA 2024", "EPA eGRID 2023", "ICAO 2023"
    source = models.CharField(max_length=100)
    # Matches EmissionRecord.category
    category = models.CharField(max_length=100)
    # e.g. "diesel", "natural_gas", "short_haul_economy", "electricity_uk"
    activity = models.CharField(max_length=100)
    # Country or grid region where applicable (blank = global)
    region = models.CharField(max_length=50, blank=True)
    # kg CO₂e per unit of activity
    factor_kg_co2e = models.DecimalField(max_digits=12, decimal_places=8)
    # Per what unit: "litre", "kWh", "km", "room_night"
    unit = models.CharField(max_length=20)
    valid_from = models.DateField()
    # Null = currently active factor
    valid_to = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.activity} ({self.source}) — {self.factor_kg_co2e} kg CO₂e/{self.unit}"

    class Meta:
        ordering = ['category', 'activity']
        indexes = [
            models.Index(fields=['category', 'activity', 'region']),
        ]


class UnitConversion(models.Model):
    """
    Simple multiply-by-factor conversion table.
    quantity_in_to_unit = quantity_in_from_unit * factor
    Seed data: L↔GAL, kWh↔MWh, mi↔km, M3↔kWh (natural gas), BTU↔kWh
    """
    from_unit = models.CharField(max_length=50)
    to_unit = models.CharField(max_length=50)
    # Multiply from_unit quantity by this to get to_unit quantity
    factor = models.DecimalField(max_digits=18, decimal_places=10)

    def __str__(self):
        return f"1 {self.from_unit} = {self.factor} {self.to_unit}"

    class Meta:
        unique_together = [('from_unit', 'to_unit')]
