"""
Management command: python manage.py seed_data

Seeds:
1. EmissionFactor table (DEFRA 2024 fuel + electricity + travel factors)
2. UnitConversion table (L↔GAL, kWh↔MWh, etc.)
3. Demo Organization: Acme Manufacturing Ltd
4. Demo DataSources (SAP, Utility, Travel)
5. Demo analyst user: analyst@acme.com / demo1234

Safe to run multiple times — uses get_or_create.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from factors.models import EmissionFactor, UnitConversion
from organizations.models import Organization
from sources.models import DataSource

User = get_user_model()

VALID_FROM = date(2024, 1, 1)

EMISSION_FACTORS = [
    # ─── Scope 1: Fuel combustion (DEFRA 2024) ───────────────────────────────
    # Source: DEFRA GHG Conversion Factors 2024, Table 1
    # Units: kg CO₂e per litre (fuel) or per m³ (natural gas) or per kWh (energy)
    {
        "source": "DEFRA 2024",
        "category": "Stationary combustion",
        "activity": "diesel",
        "region": "",
        "factor_kg_co2e": Decimal("2.51593"),  # kg CO₂e per litre
        "unit": "litre",
    },
    {
        "source": "DEFRA 2024",
        "category": "Stationary combustion",
        "activity": "petrol",
        "region": "",
        "factor_kg_co2e": Decimal("2.16840"),  # kg CO₂e per litre
        "unit": "litre",
    },
    {
        "source": "DEFRA 2024",
        "category": "Stationary combustion",
        "activity": "natural_gas",
        "region": "",
        "factor_kg_co2e": Decimal("2.02252"),  # kg CO₂e per m³
        "unit": "m3",
    },
    {
        "source": "DEFRA 2024",
        "category": "Stationary combustion",
        "activity": "lpg",
        "region": "",
        "factor_kg_co2e": Decimal("1.55540"),  # kg CO₂e per litre
        "unit": "litre",
    },
    {
        "source": "DEFRA 2024",
        "category": "Stationary combustion",
        "activity": "fuel_oil",
        "region": "",
        "factor_kg_co2e": Decimal("2.96099"),  # kg CO₂e per litre
        "unit": "litre",
    },

    # ─── Scope 2: Purchased electricity ──────────────────────────────────────
    # DEFRA 2024: UK grid average (location-based)
    {
        "source": "DEFRA 2024",
        "category": "Purchased electricity",
        "activity": "electricity_gb",
        "region": "GB",
        "factor_kg_co2e": Decimal("0.20493"),  # kg CO₂e per kWh
        "unit": "kWh",
    },
    # EPA eGRID 2023: US average
    {
        "source": "EPA eGRID 2023",
        "category": "Purchased electricity",
        "activity": "electricity_us",
        "region": "US",
        "factor_kg_co2e": Decimal("0.38600"),  # kg CO₂e per kWh (US average)
        "unit": "kWh",
    },
    # Market-based zero (renewable tariff — REGO-backed)
    {
        "source": "DEFRA 2024",
        "category": "Purchased electricity",
        "activity": "electricity_renewable",
        "region": "",
        "factor_kg_co2e": Decimal("0.00000"),
        "unit": "kWh",
    },

    # ─── Scope 3: Business travel — air (DEFRA 2024) ─────────────────────────
    # Factors already include radiative forcing (RF) multiplier of 2x
    # Short haul = < 1500 km, long haul = >= 1500 km
    {
        "source": "DEFRA 2024",
        "category": "Business travel - air",
        "activity": "short_haul_economy",
        "region": "",
        "factor_kg_co2e": Decimal("0.15100"),  # kg CO₂e per km (incl. RF)
        "unit": "km_adjusted",
    },
    {
        "source": "DEFRA 2024",
        "category": "Business travel - air",
        "activity": "short_haul_business",
        "region": "",
        "factor_kg_co2e": Decimal("0.36240"),  # 0.151 * 2.40
        "unit": "km_adjusted",
    },
    {
        "source": "DEFRA 2024",
        "category": "Business travel - air",
        "activity": "long_haul_economy",
        "region": "",
        "factor_kg_co2e": Decimal("0.19500"),  # kg CO₂e per km (incl. RF)
        "unit": "km_adjusted",
    },
    {
        "source": "DEFRA 2024",
        "category": "Business travel - air",
        "activity": "long_haul_business",
        "region": "",
        "factor_kg_co2e": Decimal("0.46800"),  # 0.195 * 2.40
        "unit": "km_adjusted",
    },

    # ─── Scope 3: Hotels (DEFRA 2024) ────────────────────────────────────────
    # kg CO₂e per room-night
    {
        "source": "DEFRA 2024",
        "category": "Business travel - hotel",
        "activity": "hotel_gb",
        "region": "GB",
        "factor_kg_co2e": Decimal("15.20000"),
        "unit": "room_night",
    },
    {
        "source": "DEFRA 2024",
        "category": "Business travel - hotel",
        "activity": "hotel_us",
        "region": "US",
        "factor_kg_co2e": Decimal("22.90000"),
        "unit": "room_night",
    },
    {
        "source": "DEFRA 2024",
        "category": "Business travel - hotel",
        "activity": "hotel_de",
        "region": "DE",
        "factor_kg_co2e": Decimal("12.40000"),
        "unit": "room_night",
    },
    {
        "source": "DEFRA 2024",
        "category": "Business travel - hotel",
        "activity": "hotel_global",  # fallback
        "region": "",
        "factor_kg_co2e": Decimal("20.00000"),
        "unit": "room_night",
    },

    # ─── Scope 3: Ground transport (DEFRA 2024) ───────────────────────────────
    {
        "source": "DEFRA 2024",
        "category": "Business travel - ground transport",
        "activity": "ground_transport",
        "region": "",
        "factor_kg_co2e": Decimal("0.16844"),  # kg CO₂e per km (average rental car)
        "unit": "km",
    },
    {
        "source": "DEFRA 2024",
        "category": "Business travel - rail",
        "activity": "rail",
        "region": "GB",
        "factor_kg_co2e": Decimal("0.03549"),  # kg CO₂e per km (UK national rail)
        "unit": "km",
    },
]

UNIT_CONVERSIONS = [
    # Fuel volume
    {"from_unit": "L", "to_unit": "GAL", "factor": Decimal("0.2641720524")},
    {"from_unit": "GAL", "to_unit": "L", "factor": Decimal("3.7854118")},
    {"from_unit": "L", "to_unit": "litre", "factor": Decimal("1.0")},
    {"from_unit": "litre", "to_unit": "L", "factor": Decimal("1.0")},
    # UK imperial gallon (≠ US gallon)
    {"from_unit": "IMPGAL", "to_unit": "L", "factor": Decimal("4.5460900")},
    {"from_unit": "L", "to_unit": "IMPGAL", "factor": Decimal("0.2199692")},
    # Electricity
    {"from_unit": "kWh", "to_unit": "MWh", "factor": Decimal("0.001")},
    {"from_unit": "MWh", "to_unit": "kWh", "factor": Decimal("1000.0")},
    # Distance
    {"from_unit": "mi", "to_unit": "km", "factor": Decimal("1.6093440")},
    {"from_unit": "km", "to_unit": "mi", "factor": Decimal("0.6213712")},
    # Natural gas
    {"from_unit": "M3", "to_unit": "kWh", "factor": Decimal("10.5500000")},  # approx, varies by calorific value
    {"from_unit": "kWh", "to_unit": "M3", "factor": Decimal("0.0947867")},
    {"from_unit": "BTU", "to_unit": "kWh", "factor": Decimal("0.0002931")},
    {"from_unit": "kWh", "to_unit": "BTU", "factor": Decimal("3412.1400")},
    {"from_unit": "MMBTU", "to_unit": "kWh", "factor": Decimal("293.07107")},
    {"from_unit": "therm", "to_unit": "kWh", "factor": Decimal("29.307107")},
]


class Command(BaseCommand):
    help = 'Seed EmissionFactor, UnitConversion, demo Organization and analyst user'

    def handle(self, *args, **options):
        self.stdout.write("Seeding EmissionFactors...")
        for ef in EMISSION_FACTORS:
            obj, created = EmissionFactor.objects.get_or_create(
                source=ef['source'],
                activity=ef['activity'],
                region=ef['region'],
                defaults={
                    'category': ef['category'],
                    'factor_kg_co2e': ef['factor_kg_co2e'],
                    'unit': ef['unit'],
                    'valid_from': VALID_FROM,
                    'valid_to': None,
                }
            )
            status = "created" if created else "exists"
            self.stdout.write(f"  {status}: {obj.activity} ({obj.source})")

        self.stdout.write("Seeding UnitConversions...")
        for uc in UNIT_CONVERSIONS:
            obj, created = UnitConversion.objects.get_or_create(
                from_unit=uc['from_unit'],
                to_unit=uc['to_unit'],
                defaults={'factor': uc['factor']}
            )
            if created:
                self.stdout.write(f"  created: {obj}")

        self.stdout.write("Creating demo Organization...")
        org, _ = Organization.objects.get_or_create(
            slug='acme-manufacturing',
            defaults={
                'name': 'Acme Manufacturing Ltd',
                'fiscal_year_start': 1,
            }
        )

        self.stdout.write("Creating demo DataSources...")
        DataSource.objects.get_or_create(
            org=org,
            display_name='Hamburg Plant Fuel (SAP MB51)',
            defaults={
                'source_type': DataSource.SourceType.SAP_FLAT_FILE,
                'scope': 'SCOPE_1',
                'config': {
                    'movement_types': ['201', '261'],
                    'emissions_materials': [],
                    'plant_map': {'0010': 'Hamburg Plant', '0020': 'Rotterdam Plant'},
                    'delimiter': ',',
                }
            }
        )
        DataSource.objects.get_or_create(
            org=org,
            display_name='HQ Electricity (National Grid)',
            defaults={
                'source_type': DataSource.SourceType.UTILITY_CSV,
                'scope': 'SCOPE_2',
                'config': {
                    'scope2_method': 'location_based',
                    'electricity_region': 'GB',
                    'exclude_meter_ids': [],
                }
            }
        )
        DataSource.objects.get_or_create(
            org=org,
            display_name='Corporate Travel (Concur)',
            defaults={
                'source_type': DataSource.SourceType.TRAVEL_CSV,
                'scope': 'SCOPE_3',
                'config': {}
            }
        )

        self.stdout.write("Creating demo analyst user...")
        user, created = User.objects.get_or_create(
            username='analyst',
            defaults={
                'email': 'analyst@acme.com',
                'first_name': 'Demo',
                'last_name': 'Analyst',
                'org': org,
                'role': User.Role.ANALYST,
            }
        )
        if created:
            user.set_password('demo1234')
            user.save()
            self.stdout.write(self.style.SUCCESS(
                "  Created analyst user: analyst@acme.com / demo1234"
            ))
        else:
            self.stdout.write("  analyst user already exists")

        self.stdout.write(self.style.SUCCESS("\n✓ Seed data complete."))
        self.stdout.write(f"  Login: analyst / demo1234")
        self.stdout.write(f"  Org: {org.name} (slug: {org.slug})")
