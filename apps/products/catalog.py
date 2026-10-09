"""Full catalog composition and navigation, using only saved priority and current facts."""
import re
from dataclasses import dataclass
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.core.paginator import EmptyPage, Paginator
from django.db.models import Case, Count, Exists, IntegerField, OuterRef, Q, Value, When
from django.http import Http404
from django.urls import reverse

from apps.recommendations.catalog_context import saved_priority
from apps.core.demo_assets import demo_image
from apps.visits.models import Visit

from .catalog_access import catalog_access
from .eligibility import catalog_candidates, product_eligibility
from .models import Category, ProductDemoPrice


def positive_id(value, field):
    value = str(value)
    if not value.isascii() or not value.isdecimal() or len(value) > 18 or int(value) < 1:
        raise ValidationError({field: "شناسه یا شماره معتبر نیست."})
    return int(value)


@dataclass(frozen=True)
class CatalogOptions:
    q: str = ""
    category_id: int | None = None
    priority: str = "all"
    page: int = 1
    page_size: int = 20
    catalog_context: str = ""

    @classmethod
    def parse(cls, query):
        q = query.get("q", "").strip()
        if len(q) > 200:
            raise ValidationError({"q": "عبارت جستجو بیش از حد طولانی است."})
        priority = query.get("priority", "all")
        if priority not in ("all", "prioritized", "ordinary"):
            raise ValidationError({"priority": "فیلتر اولویت معتبر نیست."})
        page = positive_id(query.get("page", "1"), "page")
        page_size = positive_id(query.get("page_size", "20"), "page_size")
        if page_size > 100:
            raise ValidationError({"page_size": "حداکثر تعداد محصولات در صفحه ۱۰۰ است."})
        category = query.get("category_id", "")
        category_id = positive_id(category, "category_id") if category else None
        token = query.get("catalog_context", "")
        if len(token) > 100000:
            raise ValidationError({"catalog_context": "زمینه فهرست معتبر نیست."})
        return cls(q, category_id, priority, page, page_size, token)

    def navigation_query(self, token):
        query = {"catalog_context": token, "page": self.page, "page_size": self.page_size, "priority": self.priority}
        if self.q:
            query["q"] = self.q
        if self.category_id:
            query["category_id"] = self.category_id
        return query


def _counts(queryset, prioritized_ids):
    counts = queryset.aggregate(total=Count("pk"), prioritized=Count("pk", filter=Q(pk__in=prioritized_ids)))
    return {**counts, "ordinary": counts["total"] - counts["prioritized"]}


def build_catalog(user, customer_code, visit_id, query=None):
    """Authorized zero-write service boundary used by the read API and future UI."""
    visit_id = positive_id(visit_id, "visit_id")
    access = catalog_access(user, customer_code, visit_id)
    options = CatalogOptions.parse(query or {})
    priority = saved_priority(access, options.catalog_context)
    by_product = {row.product_id: row for row in priority.recommendations}
    ids = list(by_product)
    candidates = catalog_candidates()
    overall = _counts(candidates, ids)
    categories = list(Category.objects.filter(products__is_active=True).distinct().order_by("name", "pk").values("id", "code", "name"))
    filtered = candidates
    if options.q:
        filtered = filtered.filter(
            Q(product_code__icontains=options.q) | Q(name__icontains=options.q)
            | Q(brand__name__icontains=options.q) | Q(category__name__icontains=options.q)
        )
    if options.category_id:
        filtered = filtered.filter(category_id=options.category_id)
    if options.priority == "prioritized":
        filtered = filtered.filter(pk__in=ids)
    elif options.priority == "ordinary":
        filtered = filtered.exclude(pk__in=ids)
    counts = _counts(filtered, ids)
    ordered = filtered.select_related("brand", "category", "inventory").annotate(
        _priority_order=Case(*[When(pk=pk, then=Value(index)) for index, pk in enumerate(ids)], default=Value(len(ids)), output_field=IntegerField()),
        _has_demo_price=Exists(ProductDemoPrice.objects.filter(product_id=OuterRef("pk"))),
    ).order_by("_priority_order", "product_code", "pk")
    paginator = Paginator(ordered, options.page_size)
    # Reuse the aggregate count instead of adding a pagination COUNT query.
    paginator.count = counts["total"]
    try:
        page = paginator.page(options.page)
    except EmptyPage as error:
        raise Http404 from error
    items = []
    for product in page:
        rec = by_product.get(product.pk)
        eligibility = product_eligibility(product)
        # This is quote existence only, not a valid final customer quote/provider.
        visit_editable = access.visit.status == Visit.VisitStatus.IN_PROGRESS
        can_add = eligibility["can_add"] and product._has_demo_price and visit_editable
        reason = eligibility["non_addable_reason"] or (None if product._has_demo_price else "PRICE_UNAVAILABLE")
        if reason is None and not visit_editable:
            reason = "VISIT_NOT_ACTIVE"
        brief_query = {
            "customer_code": access.customer.customer_code, "visit_id": access.visit.pk,
            "return_to": "catalog", **options.navigation_query(priority.token),
        }
        items.append({
            "product_id": product.pk, "product_code": product.product_code, "name": product.name, "unit": product.unit,
            "brand": {"id": product.brand_id, "name": product.brand.name},
            "category": {"id": product.category_id, "code": product.category.code, "name": product.category.name},
            "is_prioritized": rec is not None,
            "priority_label": "پیشنهاد اولویت‌دار" if rec else "بدون اولویت ویژه",
            "recommendation": {
                "id": rec.pk, "rank": rec.rank, "type": rec.recommendation_type,
                "short_reason": " ".join(re.split(r"(?<=[.!؟])\s+", rec.reason.strip())[:2]),
                "explanation_snapshot": rec.explanation_snapshot,
            } if rec else None,
            "catalog_visible": True, "inventory_state": eligibility["inventory_state"],
            "available_quantity": eligibility["available_quantity"], "inventory_can_add": eligibility["can_add"],
            "can_add": bool(can_add), "non_addable_reason": reason,
            "image": demo_image("products", product.product_code),
            "pricing": {"has_demo_price": product._has_demo_price, "state": "NOT_EVALUATED"},
            "brief_url": reverse("product-commercial-brief", args=[product.product_code]) + "?" + urlencode(brief_query),
        })
    return {
        "version": 1, "customer": {"id": access.customer.pk, "code": access.customer.customer_code, "name": access.customer.name},
        "visit": {"id": access.visit.pk, "status": access.visit.status},
        "catalog_context": priority.token, "counts": {"overall": overall, "filtered": counts},
        "categories": categories, "filters": {"q": options.q, "category_id": options.category_id, "priority": options.priority},
        "pagination": {"page": page.number, "page_size": options.page_size, "pages": paginator.num_pages, "has_next": page.has_next(), "has_previous": page.has_previous()},
        "items": items,
    }


def guided_catalog_return_url(user, customer, visit, product, query):
    """Validated ordinary/recommended Product Brief return; no arbitrary destination."""
    if visit is None:
        raise Http404
    access = catalog_access(user, customer.customer_code, visit.pk)
    options = CatalogOptions.parse(query)
    if not options.catalog_context or not product.is_active:
        raise Http404
    priority = saved_priority(access, options.catalog_context)
    return_query = {"visit_id": visit.pk, "product_id": product.pk, **options.navigation_query(priority.token)}
    return reverse("recommendation-presentation", args=[customer.customer_code]) + "?" + urlencode(return_query) + f"#catalog-product-{product.pk}"
