import json
import re
from typing import Optional


class FilterEngine:
    """
    Pure logic engine for matching Vinted items against user-defined filters.
    No I/O — all inputs come from the caller.
    """

    def match_item(self, item: dict, f) -> bool:
        """
        Returns True if `item` satisfies ALL criteria defined in filter `f`.
        `f` can be a DB Filter ORM object or a plain dict with the same fields.
        """
        def get(attr: str, default=None):
            if isinstance(f, dict):
                return f.get(attr, default)
            return getattr(f, attr, default)

        # Keywords check
        keywords = get("keywords")
        if keywords and not self._match_keywords(item, keywords):
            return False

        # Category check — match by ID, OR trust targeted fetch, OR reject if unknown
        category_ids = self._parse_json_list(get("category_ids"))
        if category_ids:
            item_cat_id = item.get("category_id")
            # Items tagged by poller as fetched specifically for these categories
            targeted_cat_ids = [str(c) for c in (item.get("_targeted_category_ids") or [])]

            if item_cat_id is not None and self._match_list(str(item_cat_id), [str(c) for c in category_ids]):
                pass  # exact ID match
            elif targeted_cat_ids and set(str(c) for c in category_ids) & set(targeted_cat_ids):
                pass  # item was fetched by Vinted with these category params — trust it
            else:
                return False  # no category match (wrong ID or missing info)

        # Brand check — ID match, targeted-fetch trust, text fallback, or reject
        brand_ids = self._parse_json_list(get("brand_ids"))
        if brand_ids:
            item_brand_id = str(item.get("brand_id") or "")
            # Items tagged by poller as fetched specifically for these brands
            targeted_brand_ids = [str(b) for b in (item.get("_targeted_brand_ids") or [])]

            if item_brand_id and self._match_list(item_brand_id, [str(b) for b in brand_ids]):
                pass  # exact numeric ID match
            elif targeted_brand_ids and set(str(b) for b in brand_ids) & set(targeted_brand_ids):
                pass  # fetched by Vinted with these brand params — trust it
            elif not item_brand_id:
                # No brand_id — text fallback using stored brand names
                brand_names = self._parse_json_list(get("brand_names"))
                item_brand = (item.get("brand") or "").lower().strip()
                if brand_names and item_brand:
                    if not any(
                        bn.lower() in item_brand or item_brand in bn.lower()
                        for bn in brand_names if bn
                    ):
                        return False
                else:
                    # No brand text or no brand_names to compare → reject
                    return False
            else:
                # Has a brand_id but it doesn't match any filter brand
                return False

        # Size check — match by numeric ID
        size_ids = self._parse_json_list(get("size_ids"))
        if size_ids:
            item_size_id = str(item.get("size_id") or "")
            if not self._match_list(item_size_id, [str(s) for s in size_ids]):
                return False

        # Condition check — match against code ("good") OR text ("Bon état")
        conditions = self._parse_json_list(get("conditions"))
        if conditions:
            item_condition = (item.get("condition") or "").lower()
            item_condition_code = (item.get("condition_code") or "").lower()
            matched = False
            for c in conditions:
                cl = c.lower()
                # Match by code (e.g. "good" == "good")
                if cl == item_condition_code:
                    matched = True; break
                # Match by partial text (e.g. "bon" in "bon état")
                if cl in item_condition or item_condition in cl:
                    matched = True; break
            if not matched:
                return False

        # Price check
        price_min = get("price_min")
        price_max = get("price_max")
        item_price = item.get("price")
        if item_price is not None:
            if price_min is not None and item_price < price_min:
                return False
            if price_max is not None and item_price > price_max:
                return False

        # Country check
        country_codes = self._parse_json_list(get("country_codes"))
        if country_codes:
            item_country = (item.get("country_code") or "").upper()
            if item_country not in [c.upper() for c in country_codes]:
                return False

        return True

    def get_matching_filters(self, item: dict, all_filters: list) -> list:
        """Return all filters from `all_filters` that match the item."""
        return [f for f in all_filters if self.match_item(item, f)]

    def _match_keywords(self, item: dict, keywords: str) -> bool:
        """
        Match keywords (space-separated) against item title.
        Quoted phrases are matched as-is.
        All terms must match (AND logic).
        """
        title = (item.get("title") or "").lower()
        brand = (item.get("brand") or "").lower()
        searchable = f"{title} {brand}"

        # Extract quoted phrases
        quoted = re.findall(r'"([^"]+)"', keywords)
        remaining = re.sub(r'"[^"]*"', "", keywords)
        plain_terms = remaining.split()

        for phrase in quoted:
            if phrase.lower() not in searchable:
                return False

        for term in plain_terms:
            if term and term.lower() not in searchable:
                return False

        return True

    def _match_list(self, value: str, allowed: list[str]) -> bool:
        """Check if value is in the allowed list. Empty list means no restriction."""
        if not allowed:
            return True
        return value in allowed

    def _parse_json_list(self, value) -> list:
        """Parse a JSON list string or return as-is if already a list."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, ValueError):
                return []
        return []
