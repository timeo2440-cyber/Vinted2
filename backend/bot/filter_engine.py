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

        # Category check
        category_ids = self._parse_json_list(get("category_ids"))
        if category_ids and not self._match_list(str(item.get("category_id", "")), [str(c) for c in category_ids]):
            return False

        # Brand check — match by numeric ID, with text fallback if ID missing
        brand_ids = self._parse_json_list(get("brand_ids"))
        if brand_ids:
            item_brand_id = str(item.get("brand_id") or "")
            if item_brand_id and self._match_list(item_brand_id, [str(b) for b in brand_ids]):
                pass  # matched by ID
            elif not item_brand_id:
                # No brand_id on item — fall back to text matching via brand_names
                brand_names = self._parse_json_list(get("brand_names"))
                if brand_names:
                    item_brand = (item.get("brand") or "").lower()
                    if not any(bn.lower() in item_brand or item_brand in bn.lower() for bn in brand_names if bn):
                        return False
                else:
                    # No brand_names stored either — can't match, skip brand check
                    pass
            else:
                # Has brand_id but doesn't match
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
