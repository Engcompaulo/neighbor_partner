"""Flask web layer for the Neighbor Partner app.

This module hosts the Flask application factory and HTTP routes. It
initializes and seeds the database on startup, renders the Jinja2
templates, validates registration form input, and orchestrates calls
to ``db.py`` (data access) and ``ai.py`` (partner ranking and promo
generation). It contains no SQL or AI implementation details itself.
"""
from flask import Flask, redirect, render_template, request, url_for

import ai
import db

# Order used both for validation (first missing field wins) and for the
# human-readable labels shown in the "field is required" message.
_REQUIRED_FIELDS = [
    ("name", "Name"),
    ("segment", "Segment"),
    ("target_audience", "Target audience"),
    ("neighborhood", "Neighborhood"),
]

# Maximum number of partner suggestions rendered per shop.
_MAX_PARTNERS = 3


def create_app():
    """Build and configure the Flask application.

    Initializes and seeds the database once on startup, then registers the
    routes. Returns the ready-to-serve application instance.
    """
    flask_app = Flask(__name__)

    # Create the schema and seed example shops on first run.
    db.init_db()

    @flask_app.route("/")
    def index():
        """Render the public shop list and the registration form."""
        return render_template("index.html", shops=db.list_shops())

    @flask_app.route("/shops", methods=["POST"])
    def create_shop():
        """Validate and persist a new shop, then redirect to the list.

        Reads the four required form fields. If any is empty (after
        trimming), re-renders the index with a message naming the first
        missing field and the current shop list. On success inserts the
        shop and redirects to the index.
        """
        values = {
            field: (request.form.get(field) or "").strip()
            for field, _ in _REQUIRED_FIELDS
        }

        for field, label in _REQUIRED_FIELDS:
            if not values[field]:
                return render_template(
                    "index.html",
                    shops=db.list_shops(),
                    message=f"{label} is required.",
                )

        db.insert_shop(
            values["name"],
            values["segment"],
            values["target_audience"],
            values["neighborhood"],
        )
        return redirect(url_for("index"))

    @flask_app.route("/shops/<int:shop_id>/suggestions")
    def suggestions(shop_id):
        """Render up to three AI-ranked partner suggestions for a shop.

        Redirects to the index if the shop does not exist. Candidates are
        pre-filtered by the data layer (same neighborhood, different
        segment), ranked by the AI layer, and capped at three.
        """
        shop = db.get_shop(shop_id)
        if shop is None:
            return redirect(url_for("index"))

        candidates = db.list_candidates(shop)
        partners = ai.suggest_partners(shop, candidates)[:_MAX_PARTNERS]
        return render_template("suggestions.html", shop=shop, partners=partners)

    @flask_app.route("/shops/<int:shop_id>/promo", methods=["POST"])
    def generate_promo(shop_id):
        """Generate a promo blurb for the shop and a chosen partner.

        Redirects to the index if the shop is missing. Reads ``partner_id``
        from the form; if the partner is missing the page is re-rendered
        without a promo. Otherwise the AI layer writes a blurb, and the
        suggestions page is re-rendered with the re-ranked partner cards
        and the generated text.
        """
        shop = db.get_shop(shop_id)
        if shop is None:
            return redirect(url_for("index"))

        # Re-rank candidates so the partner cards still render on this page.
        candidates = db.list_candidates(shop)
        partners = ai.suggest_partners(shop, candidates)[:_MAX_PARTNERS]

        promo = None
        partner_id = request.form.get("partner_id")
        if partner_id:
            partner = db.get_shop(partner_id)
            if partner is not None:
                promo = ai.generate_promo(shop, partner)

        return render_template(
            "suggestions.html",
            shop=shop,
            partners=partners,
            promo=promo,
        )

    return flask_app


# Module-level application object exposed for gunicorn as ``app:app``.
app = create_app()


if __name__ == "__main__":
    # Local development entry point; production uses gunicorn.
    app.run(host="0.0.0.0", port=5000)
