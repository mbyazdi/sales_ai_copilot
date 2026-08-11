import os
import sys
import random
from datetime import date, timedelta
from decimal import Decimal

import django
from django.db import models

# ============================================================
# Django Setup
# ============================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(
        os.path.abspath(__file__)
    )
)

sys.path.append(PROJECT_ROOT)

os.environ.setdefault(
    "DJANGO_SETTINGS_MODULE",
    "sales_ai_copilot.settings"
)

django.setup()


# ============================================================
# Imports
# ============================================================

from apps.customers.models import (
    Customer,
    Customer360,
    CustomerGrade,
)

from apps.products.models import (
    Brand,
    Category,
    Product,
)

from apps.sales.models import (
    Sale,
    SaleItem,
)

from apps.promotions.models import (
    Promotion,
    PromotionProduct,
)

from apps.inventory.models import (
    Inventory,
)

from apps.visits.models import (
    Salesperson,
    CustomerAssignment,
    Visit,
)


# ============================================================
# Configuration
# ============================================================

NUM_CUSTOMERS = 200
NUM_SALESPERSONS = 20
NUM_PRODUCTS = 60
NUM_SALES = 5000

RANDOM_SEED = 42

random.seed(RANDOM_SEED)


# ============================================================
# Helper Functions
# ============================================================

def money(value):
    return Decimal(str(round(value, 2)))


def random_date(start_date, end_date):
    delta = (end_date - start_date).days

    return start_date + timedelta(
        days=random.randint(0, delta)
    )


# ============================================================
# Reset Database
# ============================================================

def reset_database():

    print("\nCleaning existing demo data...")

    Visit.objects.all().delete()
    CustomerAssignment.objects.all().delete()
    Salesperson.objects.all().delete()

    Inventory.objects.all().delete()

    SaleItem.objects.all().delete()
    Sale.objects.all().delete()

    PromotionProduct.objects.all().delete()
    Promotion.objects.all().delete()

    Customer360.objects.all().delete()
    Customer.objects.all().delete()
    CustomerGrade.objects.all().delete()

    Product.objects.all().delete()
    Category.objects.all().delete()
    Brand.objects.all().delete()

    print("Database cleaned.")


# ============================================================
# Customer Grades
# ============================================================

def create_customer_grades():

    print("\nCreating customer grades...")

    grades_data = [
        (
            "A",
            "Strategic",
            "High value strategic customer",
            4,
        ),
        (
            "B",
            "High Value",
            "High value customer",
            3,
        ),
        (
            "C",
            "Medium Value",
            "Medium value customer",
            2,
        ),
        (
            "D",
            "Low Value",
            "Low value customer",
            1,
        ),
    ]

    grades = {}

    for code, name, description, priority in grades_data:

        grade = CustomerGrade.objects.create(
            code=code,
            name=name,
            description=description,
            priority=priority,
            is_active=True,
        )

        grades[code] = grade

    print(f"Created {len(grades)} customer grades.")

    return grades


# ============================================================
# Brands
# ============================================================

def create_brands():

    print("\nCreating brands...")

    brand_data = [
        ("BR01", "NovaTech"),
        ("BR02", "PowerMax"),
        ("BR03", "HomePro"),
        ("BR04", "Electra"),
        ("BR05", "SmartLife"),
        ("BR06", "VivaTech"),
        ("BR07", "ProLine"),
        ("BR08", "MaxHome"),
        ("BR09", "UltraCare"),
        ("BR10", "PrimeTech"),
    ]

    brands = []

    for code, name in brand_data:

        brand = Brand.objects.create(
            code=code,
            name=name,
            description=f"{name} electrical products",
            is_active=True,
        )

        brands.append(brand)

    print(f"Created {len(brands)} brands.")

    return brands


# ============================================================
# Categories
# ============================================================

def create_categories():

    print("\nCreating categories...")

    category_data = {
        "PERSONAL": (
            "CAT01",
            "Personal Electrical",
        ),

        "HOME": (
            "CAT02",
            "Home Appliances",
        ),
    }

    parents = {}

    for key, (code, name) in category_data.items():

        parents[key] = Category.objects.create(
            code=code,
            name=name,
            description=f"{name} products",
            parent=None,
            is_active=True,
        )

    # --------------------------------------------------------
    # Personal Electrical
    # --------------------------------------------------------

    personal_categories = [
        ("CAT11", "Hair Dryers"),
        ("CAT12", "Hair Straighteners"),
        ("CAT13", "Hair Stylers"),
        ("CAT14", "Hair Clippers"),
        ("CAT15", "Beard Trimmers"),
        ("CAT16", "Electric Shavers"),
        ("CAT17", "Epilators"),
    ]

    # --------------------------------------------------------
    # Home Appliances
    # --------------------------------------------------------

    home_categories = [
        ("CAT21", "Vacuum Cleaners"),
        ("CAT22", "Blenders"),
        ("CAT23", "Mixers"),
        ("CAT24", "Electric Irons"),
        ("CAT25", "Kettles"),
        ("CAT26", "Coffee Makers"),
        ("CAT27", "Toasters"),
    ]

    categories = []

    for code, name in personal_categories:

        category = Category.objects.create(
            code=code,
            name=name,
            parent=parents["PERSONAL"],
            description=f"{name} products",
            is_active=True,
        )

        categories.append(
            ("PERSONAL_ELECTRICAL", category)
        )

    for code, name in home_categories:

        category = Category.objects.create(
            code=code,
            name=name,
            parent=parents["HOME"],
            description=f"{name} products",
            is_active=True,
        )

        categories.append(
            ("HOME_APPLIANCE", category)
        )

    print(
        f"Created {len(categories)} subcategories."
    )

    return parents, categories


# ============================================================
# Products
# ============================================================

def create_products(brands, categories):

    print("\nCreating products...")

    personal_templates = [
        ("Hair Dryer", 25, 70),
        ("Hair Straightener", 30, 90),
        ("Hair Styler", 35, 100),
        ("Hair Clipper", 25, 80),
        ("Beard Trimmer", 20, 65),
        ("Electric Shaver", 35, 120),
        ("Epilator", 30, 100),
    ]

    home_templates = [
        ("Vacuum Cleaner", 80, 250),
        ("Blender", 35, 100),
        ("Mixer", 45, 140),
        ("Electric Iron", 30, 90),
        ("Kettle", 20, 70),
        ("Coffee Maker", 50, 160),
        ("Toaster", 30, 85),
    ]

    personal_categories = [
        category
        for group, category in categories
        if group == "PERSONAL_ELECTRICAL"
    ]

    home_categories = [
        category
        for group, category in categories
        if group == "HOME_APPLIANCE"
    ]

    products = []

    product_counter = 1

    # --------------------------------------------------------
    # Personal Electrical Products
    # --------------------------------------------------------

    for category, template in zip(
        personal_categories,
        personal_templates
    ):

        name, min_price, max_price = template

        for variant in range(1, 5):

            brand = random.choice(brands)

            product = Product.objects.create(
                product_code=f"PE{product_counter:04d}",

                name=f"{brand.name} {name} {variant}",

                brand=brand,

                category=category,

                product_group=Product.ProductGroup.PERSONAL_ELECTRICAL,

                description=(
                    f"{brand.name} {name}, "
                    f"model {variant}"
                ),

                unit="PCS",

                package_size="1 PCS",

                is_consumable=False,

                is_durable=True,

                repurchase_cycle_days=random.choice(
                    [
                        180,
                        270,
                        365,
                        540,
                    ]
                ),

                is_active=True,
            )

            # Store simulated price dynamically.
            # We will use it in sales generation.
            product.demo_price = money(
                random.uniform(
                    min_price,
                    max_price
                )
            )

            products.append(product)

            product_counter += 1

    # --------------------------------------------------------
    # Home Appliances
    # --------------------------------------------------------

    for category, template in zip(
        home_categories,
        home_templates
    ):

        name, min_price, max_price = template

        for variant in range(1, 4):

            brand = random.choice(brands)

            product = Product.objects.create(
                product_code=f"HA{product_counter:04d}",

                name=f"{brand.name} {name} {variant}",

                brand=brand,

                category=category,

                product_group=Product.ProductGroup.HOME_APPLIANCE,

                description=(
                    f"{brand.name} {name}, "
                    f"model {variant}"
                ),

                unit="PCS",

                package_size="1 PCS",

                is_consumable=False,

                is_durable=True,

                repurchase_cycle_days=random.choice(
                    [
                        365,
                        540,
                        730,
                    ]
                ),

                is_active=True,
            )

            product.demo_price = money(
                random.uniform(
                    min_price,
                    max_price
                )
            )

            products.append(product)

            product_counter += 1

    print(
        f"Created {len(products)} electrical products."
    )

    return products


# ============================================================
# Salespersons
# ============================================================

def create_salespersons():

    print("\nCreating salespersons...")

    first_names = [
        "Ali",
        "Reza",
        "Mohammad",
        "Hassan",
        "Mehdi",
        "Saeed",
        "Amir",
        "Hossein",
        "Majid",
        "Farhad",
        "Nima",
        "Pouya",
        "Arman",
        "Morteza",
        "Navid",
        "Omid",
        "Milad",
        "Shahin",
        "Hamid",
        "Mostafa",
    ]

    last_names = [
        "Ahmadi",
        "Mohammadi",
        "Karimi",
        "Hosseini",
        "Rahimi",
        "Moradi",
        "Jafari",
        "Kazemi",
        "Hashemi",
        "Sadeghi",
    ]

    salespersons = []

    for i in range(1, NUM_SALESPERSONS + 1):

        salesperson = Salesperson.objects.create(
            employee_code=f"SP{i:03d}",

            first_name=first_names[i - 1],

            last_name=random.choice(
                last_names
            ),

            phone=f"09{random.randint(100000000, 999999999)}",

            is_active=True,
        )

        salespersons.append(salesperson)

    print(
        f"Created {len(salespersons)} salespersons."
    )

    return salespersons


# ============================================================
# Customers
# ============================================================

def create_customers(grades):

    print("\nCreating customers...")

    cities = [
        "Tehran",
        "Karaj",
        "Mashhad",
        "Isfahan",
        "Shiraz",
        "Tabriz",
        "Qom",
        "Rasht",
        "Ahvaz",
        "Kerman",
    ]

    customer_types = [
        Customer.CustomerType.STORE,
        Customer.CustomerType.SALON,
        Customer.CustomerType.DISTRIBUTOR,
        Customer.CustomerType.OTHER,
    ]

    customers = []

    # --------------------------------------------------------
    # Distribution of grades
    # --------------------------------------------------------

    grade_pool = (
        ["A"] * 40 +
        ["B"] * 60 +
        ["C"] * 70 +
        ["D"] * 30
    )

    random.shuffle(grade_pool)

    for i in range(1, NUM_CUSTOMERS + 1):

        grade_code = grade_pool[i - 1]

        customer = Customer.objects.create(
            customer_code=f"C{i:04d}",

            name=f"Customer Store {i:03d}",

            customer_type=random.choice(
                customer_types
            ),

            grade=grades[grade_code],

            city=random.choice(cities),

            address=(
                f"Demo Address {i:03d}"
            ),

            phone=(
                f"021{random.randint(10000000, 99999999)}"
            ),

            is_active=True,
        )

        customers.append(customer)

    print(
        f"Created {len(customers)} customers."
    )

    return customers


# ============================================================
# Customer Assignments
# ============================================================

def create_assignments(
    customers,
    salespersons
):

    print("\nAssigning customers to salespersons...")

    assignments = []

    start_date = date.today() - timedelta(
        days=365
    )

    for i, customer in enumerate(customers):

        salesperson = salespersons[
            i % len(salespersons)
        ]

        assignment = CustomerAssignment.objects.create(
            salesperson=salesperson,

            customer=customer,

            start_date=start_date,

            end_date=None,

            is_active=True,
        )

        assignments.append(assignment)

    print(
        f"Created {len(assignments)} customer assignments."
    )

    return assignments


# ============================================================
# Customer Profiles
# ============================================================

def create_customer_profiles(customers):

    """
    Creates hidden behavioral profiles for demo generation.

    These profiles are NOT stored in the database.

    They control how sales are generated.
    """

    profiles = {}

    for customer in customers:

        profile = random.choice(
            [
                "PERSONAL_ELECTRICAL",
                "PERSONAL_ELECTRICAL",
                "HOME_APPLIANCE",
                "HOME_APPLIANCE",
                "MIXED",
                "HIGH_VALUE",
                "AT_RISK",
            ]
        )

        profiles[customer.id] = profile

    # Make several deterministic demo scenarios.

    for index, customer in enumerate(customers):

        if index % 20 == 0:
            profiles[customer.id] = "PERSONAL_ELECTRICAL"

        elif index % 25 == 0:
            profiles[customer.id] = "HOME_APPLIANCE"

        elif index % 30 == 0:
            profiles[customer.id] = "AT_RISK"

    return profiles


# ============================================================
# Product Groups for Recommendation Simulation
# ============================================================

def build_product_groups(products):

    groups = {
        "PERSONAL_ELECTRICAL": [],
        "HOME_APPLIANCE": [],
    }

    for product in products:

        if product.product_group == (
            Product.ProductGroup.PERSONAL_ELECTRICAL
        ):
            groups["PERSONAL_ELECTRICAL"].append(product)

        elif product.product_group == (
            Product.ProductGroup.HOME_APPLIANCE
        ):
            groups["HOME_APPLIANCE"].append(product)

    return groups


# ============================================================
# Sales Generation
# ============================================================

def create_sales(
    customers,
    products,
    profiles
):

    print("\nCreating sales...")

    product_groups = build_product_groups(
        products
    )

    start_date = date.today() - timedelta(
        days=365
    )

    end_date = date.today()

    sales_created = 0
    items_created = 0

    personal_products = product_groups[
        "PERSONAL_ELECTRICAL"
    ]

    home_products = product_groups[
        "HOME_APPLIANCE"
    ]

    for sale_index in range(
        1,
        NUM_SALES + 1
    ):

        customer = random.choice(
            customers
        )

        profile = profiles[
            customer.id
        ]

        # ----------------------------------------------------
        # Purchase date
        # ----------------------------------------------------

        sale_date = random_date(
            start_date,
            end_date
        )

        # ----------------------------------------------------
        # Select preferred product group
        # ----------------------------------------------------

        if profile == "PERSONAL_ELECTRICAL":

            primary_pool = personal_products

        elif profile == "HOME_APPLIANCE":

            primary_pool = home_products

        elif profile == "AT_RISK":

            # Old purchases for at-risk customers
            # are deliberately generated more often.
            sale_date = random_date(
                start_date,
                date.today() - timedelta(days=45)
            )

            primary_pool = random.choice(
                [
                    personal_products,
                    home_products,
                ]
            )

        else:

            primary_pool = random.choice(
                [
                    personal_products,
                    home_products,
                ]
            )

        # ----------------------------------------------------
        # Number of products in basket
        # ----------------------------------------------------

        number_of_items = random.randint(
            1,
            4
        )

        selected_products = random.sample(
            primary_pool,
            min(
                number_of_items,
                len(primary_pool)
            )
        )

        total_amount = Decimal("0")

        sale_items_data = []

        for product in selected_products:

            quantity = random.randint(
                1,
                3
            )

            unit_price = product.demo_price

            line_total = (
                unit_price *
                quantity
            )

            total_amount += line_total

            sale_items_data.append(
                (
                    product,
                    quantity,
                    unit_price,
                    line_total,
                )
            )

        discount = Decimal("0")

        # Occasionally apply a discount.
        if random.random() < 0.15:

            discount = (
                total_amount *
                Decimal("0.05")
            )

        net_amount = (
            total_amount -
            discount
        )

        sale = Sale.objects.create(
            invoice_number=(
                f"INV{sale_index:06d}"
            ),

            customer=customer,

            sale_date=sale_date,

            total_amount=total_amount,

            discount_amount=discount,

            net_amount=net_amount,
        )

        sales_created += 1

        for (
            product,
            quantity,
            unit_price,
            line_total,
        ) in sale_items_data:

            SaleItem.objects.create(
                sale=sale,

                product=product,

                quantity=quantity,

                unit_price=unit_price,

                discount_amount=Decimal("0"),

                total_amount=line_total,
            )

            items_created += 1

    print(
        f"Created {sales_created} sales."
    )

    print(
        f"Created approximately "
        f"{items_created} sale items."
    )


# ============================================================
# Inventory
# ============================================================

def create_inventory(products):

    print("\nCreating inventory...")

    inventories = []

    for product in products:

        # Some products deliberately have low stock.
        if random.random() < 0.10:

            available = random.randint(
                0,
                10
            )

        else:

            available = random.randint(
                20,
                300
            )

        reserved = random.randint(
            0,
            min(available, 10)
        )

        minimum_stock = random.randint(
            5,
            20
        )

        inventory = Inventory.objects.create(
            product=product,

            available_quantity=available,

            reserved_quantity=reserved,

            minimum_stock=minimum_stock,
        )

        inventories.append(inventory)

    print(
        f"Created {len(inventories)} inventory records."
    )

    return inventories


# ============================================================
# Promotions
# ============================================================

def create_promotions(
    products,
    grades
):

    print("\nCreating promotions...")

    promotions = []

    today = date.today()

    # --------------------------------------------------------
    # Promotion 1
    # --------------------------------------------------------

    promotion = Promotion.objects.create(
        name="Personal Electrical Special Offer",

        code="PROMO-PE-01",

        promotion_type=(
            Promotion.PromotionType.PERCENTAGE
        ),

        start_date=today - timedelta(days=30),

        end_date=today + timedelta(days=30),

        discount_percent=Decimal("10"),

        minimum_quantity=1,

        description=(
            "10 percent discount on selected "
            "personal electrical products."
        ),

        is_active=True,
    )

    promotion.customer_grades.set(
        [
            grades["A"],
            grades["B"],
        ]
    )

    selected = random.sample(
        [
            p
            for p in products
            if p.product_group == (
                Product.ProductGroup.PERSONAL_ELECTRICAL
            )
        ],
        8
    )

    for product in selected:

        PromotionProduct.objects.create(
            promotion=promotion,
            product=product,
            priority=1,
        )

    promotions.append(promotion)

    # --------------------------------------------------------
    # Promotion 2
    # --------------------------------------------------------

    promotion = Promotion.objects.create(
        name="Home Appliance Volume Offer",

        code="PROMO-HA-01",

        promotion_type=(
            Promotion.PromotionType.PERCENTAGE
        ),

        start_date=today - timedelta(days=15),

        end_date=today + timedelta(days=45),

        discount_percent=Decimal("7"),

        minimum_quantity=2,

        description=(
            "7 percent discount for selected "
            "home appliances."
        ),

        is_active=True,
    )

    promotion.customer_grades.set(
        [
            grades["A"],
            grades["B"],
            grades["C"],
        ]
    )

    selected = random.sample(
        [
            p
            for p in products
            if p.product_group == (
                Product.ProductGroup.HOME_APPLIANCE
            )
        ],
        8
    )

    for product in selected:

        PromotionProduct.objects.create(
            promotion=promotion,
            product=product,
            priority=1,
        )

    promotions.append(promotion)

    # --------------------------------------------------------
    # Promotion 3
    # --------------------------------------------------------

    promotion = Promotion.objects.create(
        name="Premium Customer Promotion",

        code="PROMO-PREMIUM-01",

        promotion_type=(
            Promotion.PromotionType.PERCENTAGE
        ),

        start_date=today - timedelta(days=10),

        end_date=today + timedelta(days=20),

        discount_percent=Decimal("12"),

        minimum_quantity=1,

        description=(
            "Special promotion for strategic "
            "customers."
        ),

        is_active=True,
    )

    promotion.customer_grades.set(
        [
            grades["A"],
        ]
    )

    selected = random.sample(
        products,
        6
    )

    for product in selected:

        PromotionProduct.objects.create(
            promotion=promotion,
            product=product,
            priority=2,
        )

    promotions.append(promotion)

    print(
        f"Created {len(promotions)} promotions."
    )

    return promotions


# ============================================================
# Visits
# ============================================================

def create_visits(
    customers,
    salespersons
):

    print("\nCreating visits...")

    request_examples = [
        (
            "Customer is looking for a new "
            "professional hair clipper."
        ),

        (
            "Customer asked about electric "
            "shavers with better battery life."
        ),

        (
            "Customer wants affordable home "
            "appliances for a new store section."
        ),

        (
            "Customer is interested in premium "
            "hair dryers."
        ),

        (
            "Customer requested information about "
            "new vacuum cleaner models."
        ),

        (
            "Customer wants products with good "
            "after-sales support."
        ),
    ]

    feedback_examples = [
        "Customer showed positive interest.",
        "Customer requested a quotation.",
        "Customer needs more product information.",
        "Customer will decide during next visit.",
        "Customer compared products with competitors.",
    ]

    today = date.today()

    visits_created = 0

    # Approximately 50% of customers have recent visits.

    for customer_index, customer in enumerate(
        customers
    ):

        if customer_index % 2 != 0:
            continue

        salesperson = salespersons[
            customer_index % len(salespersons)
        ]

        visit_date = today - timedelta(
            days=random.randint(0, 60)
        )

        order_created = (
            random.random() < 0.35
        )

        order_amount = Decimal("0")

        if order_created:

            order_amount = money(
                random.uniform(
                    500,
                    5000
                )
            )

        follow_up_required = (
            random.random() < 0.30
        )

        follow_up_date = None

        if follow_up_required:

            follow_up_date = (
                today +
                timedelta(
                    days=random.randint(
                        3,
                        30
                    )
                )
            )

        Visit.objects.create(

            salesperson=salesperson,

            customer=customer,

            visit_date=visit_date,

            status=Visit.VisitStatus.COMPLETED,

            customer_request=random.choice(
                request_examples
            ),

            customer_feedback=random.choice(
                feedback_examples
            ),

            competitor_information=(
                "Customer mentioned competitor "
                "products during discussion."
                if random.random() < 0.25
                else ""
            ),

            notes=(
                "Demo visit generated automatically."
            ),

            order_created=order_created,

            order_amount=order_amount,

            follow_up_required=follow_up_required,

            follow_up_date=follow_up_date,
        )

        visits_created += 1

    print(
        f"Created {visits_created} visits."
    )


# ============================================================
# Customer 360 Calculation
# ============================================================

def calculate_customer_360(customers):

    print("\nCalculating Customer 360...")

    today = date.today()

    for customer in customers:

        sales = Sale.objects.filter(
            customer=customer
        )

        sale_count = sales.count()

        # ----------------------------------------------------
        # No sales
        # ----------------------------------------------------

        if sale_count == 0:

            Customer360.objects.update_or_create(
                customer=customer,

                defaults={
                    "segment": Customer360.Segment.NEW,

                    "total_orders": 0,

                    "total_items": 0,

                    "total_sales_amount": 0,

                    "average_order_value": 0,

                    "days_since_last_purchase": 0,

                    "rfm_score": 0,

                    "calculated_at": today,
                }
            )

            continue

        # ----------------------------------------------------
        # Basic calculations
        # ----------------------------------------------------

        total_sales = sum(
            (
                sale.net_amount
                for sale in sales
            ),
            Decimal("0")
        )

        total_items = sum(
            (
                sale.items.aggregate(
                    total=models.Sum("quantity")
                )["total"] or 0
                for sale in sales
            )
        )

        first_purchase = min(
            sale.sale_date
            for sale in sales
        )

        last_purchase = max(
            sale.sale_date
            for sale in sales
        )

        days_since_last = (
            today - last_purchase
        ).days

        average_order = (
            total_sales / sale_count
        )

        # ----------------------------------------------------
        # Purchase frequency
        # ----------------------------------------------------

        days_active = max(
            (
                last_purchase -
                first_purchase
            ).days,
            1
        )

        purchase_frequency = (
            sale_count /
            days_active *
            30
        )

        # ----------------------------------------------------
        # Sales windows
        # ----------------------------------------------------

        sales_30d = sum(
            (
                sale.net_amount
                for sale in sales
                if sale.sale_date >= (
                    today -
                    timedelta(days=30)
                )
            ),
            Decimal("0")
        )

        sales_90d = sum(
            (
                sale.net_amount
                for sale in sales
                if sale.sale_date >= (
                    today -
                    timedelta(days=90)
                )
            ),
            Decimal("0")
        )

        previous_30d = sum(
            (
                sale.net_amount
                for sale in sales
                if (
                    today -
                    timedelta(days=60)
                )
                <= sale.sale_date
                < (
                    today -
                    timedelta(days=30)
                )
            ),
            Decimal("0")
        )

        previous_90d = sum(
            (
                sale.net_amount
                for sale in sales
                if (
                    today -
                    timedelta(days=180)
                )
                <= sale.sale_date
                < (
                    today -
                    timedelta(days=90)
                )
            ),
            Decimal("0")
        )

        # ----------------------------------------------------
        # Trend calculations
        # ----------------------------------------------------

        if previous_30d > 0:

            change_30d = (
                (
                    sales_30d -
                    previous_30d
                )
                /
                previous_30d
                *
                100
            )

        else:

            change_30d = Decimal("0")

        if previous_90d > 0:

            change_90d = (
                (
                    sales_90d -
                    previous_90d
                )
                /
                previous_90d
                *
                100
            )

        else:

            change_90d = Decimal("0")

        # ----------------------------------------------------
        # RFM scores
        # ----------------------------------------------------

        if days_since_last <= 30:
            recency_score = 5

        elif days_since_last <= 60:
            recency_score = 4

        elif days_since_last <= 120:
            recency_score = 3

        elif days_since_last <= 240:
            recency_score = 2

        else:
            recency_score = 1

        if sale_count >= 40:
            frequency_score = 5

        elif sale_count >= 25:
            frequency_score = 4

        elif sale_count >= 15:
            frequency_score = 3

        elif sale_count >= 7:
            frequency_score = 2

        else:
            frequency_score = 1

        if total_sales >= 50000:
            monetary_score = 5

        elif total_sales >= 30000:
            monetary_score = 4

        elif total_sales >= 15000:
            monetary_score = 3

        elif total_sales >= 5000:
            monetary_score = 2

        else:
            monetary_score = 1

        rfm_score = (
            recency_score +
            frequency_score +
            monetary_score
        )

        # ----------------------------------------------------
        # Segment
        # ----------------------------------------------------

        if days_since_last > 180:

            segment = Customer360.Segment.INACTIVE

        elif (
            change_90d < -30
            and total_sales >= 15000
        ):

            segment = Customer360.Segment.AT_RISK

        elif (
            total_sales >= 30000
            and frequency_score >= 4
        ):

            segment = Customer360.Segment.HIGH_VALUE

        elif change_90d > 20:

            segment = Customer360.Segment.GROWTH

        else:

            segment = Customer360.Segment.STABLE

        # ----------------------------------------------------
        # Top product
        # ----------------------------------------------------

        product_counts = {}

        for sale in sales:

            for item in sale.items.select_related(
                "product"
            ).all():

                product_counts[
                    item.product.product_code
                ] = (
                    product_counts.get(
                        item.product.product_code,
                        0
                    )
                    +
                    item.quantity
                )

        top_product_code = ""

        if product_counts:

            top_product_code = max(
                product_counts,
                key=product_counts.get
            )

        # ----------------------------------------------------
        # Top category
        # ----------------------------------------------------

        category_counts = {}

        for sale in sales:

            for item in sale.items.select_related(
                "product__category"
            ).all():

                category_name = (
                    item.product.category.name
                )

                category_counts[
                    category_name
                ] = (
                    category_counts.get(
                        category_name,
                        0
                    )
                    +
                    item.quantity
                )

        top_category = ""

        if category_counts:

            top_category = max(
                category_counts,
                key=category_counts.get
            )

        # ----------------------------------------------------
        # Save Customer360
        # ----------------------------------------------------

        Customer360.objects.update_or_create(

            customer=customer,

            defaults={

                "total_orders": sale_count,

                "total_items": total_items,

                "total_sales_amount": total_sales,

                "average_order_value": average_order,

                "last_purchase_date": last_purchase,

                "first_purchase_date": first_purchase,

                "purchase_frequency": purchase_frequency,

                "days_since_last_purchase": days_since_last,

                "recency_score": recency_score,

                "frequency_score": frequency_score,

                "monetary_score": monetary_score,

                "rfm_score": rfm_score,

                "segment": segment,

                "top_category": top_category,

                "top_product_code": top_product_code,

                "sales_30d": sales_30d,

                "sales_90d": sales_90d,

                "sales_30d_change_percent": change_30d,

                "sales_90d_change_percent": change_90d,
            }
        )

    print("Customer 360 calculated.")


# ============================================================
# Main
# ============================================================

def main():

    print("=" * 60)

    print(
        "SALES AI COPILOT - DEMO DATA GENERATOR"
    )

    print("=" * 60)

    print(
        "\nIMPORTANT:"
    )

    print(
        "This demo generates ONLY electrical products."
    )

    print(
        "No beauty or personal-care products will be created."
    )

    reset_database()

    grades = create_customer_grades()

    brands = create_brands()

    _, categories = create_categories()

    products = create_products(
        brands,
        categories
    )

    salespersons = create_salespersons()

    customers = create_customers(
        grades
    )

    create_assignments(
        customers,
        salespersons
    )

    profiles = create_customer_profiles(
        customers
    )

    create_sales(
        customers,
        products,
        profiles
    )

    create_inventory(
        products
    )

    create_promotions(
        products,
        grades
    )

    create_visits(
        customers,
        salespersons
    )

    calculate_customer_360(
        customers
    )

    print("\n" + "=" * 60)

    print(
        "DEMO DATA GENERATION COMPLETED"
    )

    print("=" * 60)

    print(
        f"\nCustomers: {Customer.objects.count()}"
    )

    print(
        f"Salespersons: {Salesperson.objects.count()}"
    )

    print(
        f"Products: {Product.objects.count()}"
    )

    print(
        f"Sales: {Sale.objects.count()}"
    )

    print(
        f"Sale Items: {SaleItem.objects.count()}"
    )

    print(
        f"Promotions: {Promotion.objects.count()}"
    )

    print(
        f"Inventory: {Inventory.objects.count()}"
    )

    print(
        f"Visits: {Visit.objects.count()}"
    )

    print(
        f"Customer 360: {Customer360.objects.count()}"
    )

    print("\nDone.")


if __name__ == "__main__":
    main()