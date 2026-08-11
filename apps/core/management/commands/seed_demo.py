from datetime import date, timedelta
from decimal import Decimal
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.customers.models import Customer, CustomerGrade
from apps.products.models import Brand, Category, Product
from apps.sales.models import Sale, SaleItem


class Command(BaseCommand):
    help = "Create demo data for the electrical appliances business"

    @transaction.atomic
    def handle(self, *args, **options):

        self.stdout.write(
            self.style.SUCCESS(
                "Creating electrical-appliance demo data..."
            )
        )

        random.seed(42)

        # =========================================================
        # 1. CUSTOMER GRADES
        # =========================================================

        grades = [
            {
                "code": "A",
                "name": "Strategic",
                "description": "High-value strategic customer",
                "priority": 4,
            },
            {
                "code": "B",
                "name": "High Value",
                "description": "High-value customer",
                "priority": 3,
            },
            {
                "code": "C",
                "name": "Medium Value",
                "description": "Medium-value customer",
                "priority": 2,
            },
            {
                "code": "D",
                "name": "Low Value",
                "description": "Low-value customer",
                "priority": 1,
            },
        ]

        grade_objects = {}

        for data in grades:
            grade, _ = CustomerGrade.objects.update_or_create(
                code=data["code"],
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "priority": data["priority"],
                    "is_active": True,
                },
            )

            grade_objects[data["code"]] = grade

        self.stdout.write("Customer grades created.")

        # =========================================================
        # 2. BRANDS
        # =========================================================

        brands_data = [
            ("PHILIPS", "Philips"),
            ("BRAUN", "Braun"),
            ("BOSCH", "Bosch"),
            ("TEFAL", "Tefal"),
            ("PANASONIC", "Panasonic"),
            ("ROWENTA", "Rowenta"),
        ]

        brands = {}

        for code, name in brands_data:
            brand, _ = Brand.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "description": f"{name} electrical appliances",
                    "is_active": True,
                },
            )

            brands[code] = brand

        self.stdout.write("Brands created.")

        # =========================================================
        # 3. CATEGORIES
        # =========================================================

        personal_electrical, _ = Category.objects.update_or_create(
            code="PERSONAL_ELECTRICAL",
            defaults={
                "name": "Personal Electrical",
                "parent": None,
                "description": "Personal electrical appliances",
                "is_active": True,
            },
        )

        home_appliance, _ = Category.objects.update_or_create(
            code="HOME_APPLIANCE",
            defaults={
                "name": "Home Appliances",
                "parent": None,
                "description": "Electrical home appliances",
                "is_active": True,
            },
        )

        personal_categories = [
            ("HAIR_DRYER", "Hair Dryer"),
            ("HAIR_STRAIGHTENER", "Hair Straightener"),
            ("HAIR_CURLER", "Hair Curler"),
            ("ELECTRIC_SHAVER", "Electric Shaver"),
            ("TRIMMER", "Trimmer"),
            ("ELECTRIC_TOOTHBRUSH", "Electric Toothbrush"),
        ]

        home_categories = [
            ("VACUUM_CLEANER", "Vacuum Cleaner"),
            ("STEAM_IRON", "Steam Iron"),
            ("BLENDER", "Blender"),
            ("ELECTRIC_KETTLE", "Electric Kettle"),
            ("AIR_FRYER", "Air Fryer"),
            ("COFFEE_MAKER", "Coffee Maker"),
        ]

        categories = {}

        for code, name in personal_categories:
            category, _ = Category.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "parent": personal_electrical,
                    "description": name,
                    "is_active": True,
                },
            )

            categories[code] = category

        for code, name in home_categories:
            category, _ = Category.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "parent": home_appliance,
                    "description": name,
                    "is_active": True,
                },
            )

            categories[code] = category

        self.stdout.write("Electrical categories created.")

        # =========================================================
        # 4. PRODUCTS
        # =========================================================

        products_data = [
            # Personal Electrical
            (
                "PHD001",
                "Philips Hair Dryer 2100W",
                "PHILIPS",
                "HAIR_DRYER",
                "PERSONAL_ELECTRICAL",
                Decimal("85"),
            ),
            (
                "PHS001",
                "Philips Hair Straightener",
                "PHILIPS",
                "HAIR_STRAIGHTENER",
                "PERSONAL_ELECTRICAL",
                Decimal("110"),
            ),
            (
                "BRN001",
                "Braun Electric Shaver Series 3",
                "BRAUN",
                "ELECTRIC_SHAVER",
                "PERSONAL_ELECTRICAL",
                Decimal("145"),
            ),
            (
                "BRN002",
                "Braun Beard Trimmer",
                "BRAUN",
                "TRIMMER",
                "PERSONAL_ELECTRICAL",
                Decimal("95"),
            ),
            (
                "PAN001",
                "Panasonic Hair Curler",
                "PANASONIC",
                "HAIR_CURLER",
                "PERSONAL_ELECTRICAL",
                Decimal("120"),
            ),
            (
                "PHI002",
                "Philips Electric Toothbrush",
                "PHILIPS",
                "ELECTRIC_TOOTHBRUSH",
                "PERSONAL_ELECTRICAL",
                Decimal("75"),
            ),

            # Home Appliances
            (
                "BOS001",
                "Bosch Vacuum Cleaner",
                "BOSCH",
                "VACUUM_CLEANER",
                "HOME_APPLIANCE",
                Decimal("320"),
            ),
            (
                "TEF001",
                "Tefal Steam Iron",
                "TEFAL",
                "STEAM_IRON",
                "HOME_APPLIANCE",
                Decimal("135"),
            ),
            (
                "BOS002",
                "Bosch Blender",
                "BOSCH",
                "BLENDER",
                "HOME_APPLIANCE",
                Decimal("160"),
            ),
            (
                "PHI003",
                "Philips Electric Kettle",
                "PHILIPS",
                "ELECTRIC_KETTLE",
                "HOME_APPLIANCE",
                Decimal("90"),
            ),
            (
                "TEF002",
                "Tefal Air Fryer",
                "TEFAL",
                "AIR_FRYER",
                "HOME_APPLIANCE",
                Decimal("240"),
            ),
            (
                "ROW001",
                "Rowenta Coffee Maker",
                "ROWENTA",
                "COFFEE_MAKER",
                "HOME_APPLIANCE",
                Decimal("190"),
            ),
        ]

        products = []

        for (
            code,
            name,
            brand_code,
            category_code,
            product_group,
            price,
        ) in products_data:

            product, _ = Product.objects.update_or_create(
                product_code=code,
                defaults={
                    "name": name,
                    "brand": brands[brand_code],
                    "category": categories[category_code],
                    "product_group": product_group,
                    "description": name,
                    "unit": "PCS",
                    "package_size": "1 PCS",
                    "is_consumable": False,
                    "is_durable": True,
                    "repurchase_cycle_days": None,
                    "is_active": True,
                },
            )

            products.append(
                {
                    "product": product,
                    "price": price,
                }
            )

        self.stdout.write("Electrical products created.")

        # =========================================================
        # 5. CUSTOMERS
        # =========================================================

        cities = [
            "Amsterdam",
            "Rotterdam",
            "Utrecht",
            "The Hague",
            "Eindhoven",
        ]

        customer_types = [
            Customer.CustomerType.ELECTRICAL_STORE,
            Customer.CustomerType.HOME_APPLIANCE_STORE,
            Customer.CustomerType.WHOLESALER,
            Customer.CustomerType.DISTRIBUTOR,
        ]

        customers = []

        for i in range(1, 31):

            customer_code = f"C{i:04d}"

            grade_code = random.choices(
                ["A", "B", "C", "D"],
                weights=[10, 25, 45, 20],
                k=1,
            )[0]

            customer, _ = Customer.objects.update_or_create(
                customer_code=customer_code,
                defaults={
                    "name": f"Electrical Customer {i:02d}",
                    "customer_type": random.choice(customer_types),
                    "grade": grade_objects[grade_code],
                    "city": random.choice(cities),
                    "address": f"Electrical Business Street {i}",
                    "phone": f"+31-20-{1000000 + i}",
                    "is_active": True,
                },
            )

            customers.append(customer)

        self.stdout.write(
            f"{len(customers)} electrical customers created."
        )

        # =========================================================
        # 6. SALES
        # =========================================================

        today = date.today()

        invoice_counter = 1

        for customer in customers:

            # Different purchasing behavior per customer
            order_count = random.randint(5, 25)

            for _ in range(order_count):

                days_ago = random.randint(0, 180)

                sale_date = today - timedelta(
                    days=days_ago
                )

                invoice_number = (
                    f"INV-{invoice_counter:06d}"
                )

                sale = Sale.objects.create(
                    customer=customer,
                    invoice_number=invoice_number,
                    sale_date=sale_date,
                    total_amount=Decimal("0"),
                    description="Electrical appliance sale",
                )

                item_count = random.randint(1, 4)

                selected_products = random.sample(
                    products,
                    min(item_count, len(products)),
                )

                total_sale = Decimal("0")

                for item in selected_products:

                    quantity = random.randint(1, 4)

                    unit_price = item["price"]

                    gross = (
                        Decimal(quantity)
                        * unit_price
                    )

                    discount = Decimal(
                        random.choice(
                            [0, 0, 0, 5, 10, 15]
                        )
                    )

                    if discount > gross:
                        discount = Decimal("0")

                    SaleItem.objects.create(
                        sale=sale,
                        product=item["product"],
                        quantity=quantity,
                        unit_price=unit_price,
                        discount_amount=discount,
                    )

                    total_sale += (
                        gross - discount
                    )

                sale.total_amount = total_sale
                sale.save(
                    update_fields=[
                        "total_amount",
                        "updated_at",
                    ]
                )

                invoice_counter += 1

        self.stdout.write(
            f"{Sale.objects.count()} sales created."
        )

        self.stdout.write(
            f"{SaleItem.objects.count()} sale items created."
        )

        # =========================================================
        # FINISHED
        # =========================================================

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Electrical appliance demo data created successfully."
            )
        )

        self.stdout.write("")
        self.stdout.write(
            f"Customers : {Customer.objects.count()}"
        )

        self.stdout.write(
            f"Brands    : {Brand.objects.count()}"
        )

        self.stdout.write(
            f"Categories: {Category.objects.count()}"
        )

        self.stdout.write(
            f"Products  : {Product.objects.count()}"
        )

        self.stdout.write(
            f"Sales     : {Sale.objects.count()}"
        )

        self.stdout.write(
            f"Sale Items: {SaleItem.objects.count()}"
        )