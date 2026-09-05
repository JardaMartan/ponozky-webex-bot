import os
from typing import List, Dict, Any, Optional

DEFAULT_BANNER_URL = "https://images.unsplash.com/photo-1586350977771-b3b0abd50c82?w=800&auto=format&fit=crop&q=80"


def build_choice_options(catalog: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Builds the list of {title, value} options used by the Adaptive Card's
    Input.ChoiceSet."""
    choices = []
    seen_combinations = set()
    for item in catalog:
        model = item.get("model", "Ponožky")
        size = item.get("size", "Univerzální")
        stock = item.get("stock", 0)

        val = f"{model} | Velikost: {size}"
        if val not in seen_combinations:
            seen_combinations.add(val)
            # Keep the radio button label short so it fits on one line in the Webex client.
            short_model = model[:32].rstrip() + "…" if len(model) > 32 else model
            stock_label = f"{stock} ks" if stock > 0 else "Vyprodáno"
            choices.append({
                "title": f"{short_model} ({size}) · {stock_label}",
                "value": f"{model}###{size}"
            })

    if not choices:
        choices = [
            {"title": "🧦 DLOUHÉ (38-42)", "value": "Klasické dlouhé ponožky###38-42"},
            {"title": "🧦 DLOUHÉ (43-47)", "value": "Klasické dlouhé ponožky###43-47"},
            {"title": "👟 NÍZKÉ (38-42)", "value": "Nízké kotníkové ponožky###38-42"},
            {"title": "👟 NÍZKÉ (43-47)", "value": "Nízké kotníkové ponožky###43-47"}
        ]
    return choices


def build_socks_card(catalog: List[Dict[str, Any]], banner_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Dynamically generates a Webex Adaptive Card from the catalog items.
    Displays product images, descriptions, stock, and an interactive form.
    """
    banner = banner_url or os.getenv("BANNER_URL", DEFAULT_BANNER_URL)

    # Build choices from catalog (only include in-stock items, or indicate low stock)
    choices = build_choice_options(catalog)

    # Collect preview cards for distinct models
    model_previews: Dict[str, Dict[str, Any]] = {}

    for item in catalog:
        model = item.get("model", "Ponožky")
        img = item.get("image_url", "")
        desc = item.get("description", "")

        if model not in model_previews and img:
            model_previews[model] = {
                "image": img,
                "desc": desc
            }

    # If no choices available from sheet, fallback to standard options
    # (already handled inside build_choice_options)

    # Build body elements
    body: List[Dict[str, Any]] = [
        {
            "type": "Image",
            "url": banner,
            "size": "Stretch",
            "horizontalAlignment": "Center",
            "altText": "Firemní ponožky banner"
        },
        {
            "type": "TextBlock",
            "text": "🧦 Výběr firemních ponožek",
            "weight": "Bolder",
            "size": "Large",
            "horizontalAlignment": "Center",
            "spacing": "Medium",
            "color": "Accent"
        },
        {
            "type": "TextBlock",
            "text": "Vyber si model a velikost ponožek. Objednávka se automaticky zaznamená a dostaneš potvrzení.",
            "wrap": True,
            "spacing": "Small"
        }
    ]

    # Add model preview images & descriptions in columns
    if model_previews:
        preview_columns = []
        for model_name, info in list(model_previews.items())[:3]: # limit to top 3 models for visual clarity
            col_items = []
            if info.get("image"):
                col_items.append({
                    "type": "Image",
                    "url": info["image"],
                    "size": "Medium",
                    "style": "Default"
                })
            col_items.append({
                "type": "TextBlock",
                "text": model_name,
                "weight": "Bolder",
                "size": "Small",
                "wrap": True
            })
            if info.get("desc"):
                col_items.append({
                    "type": "TextBlock",
                    "text": info["desc"][:80] + ("..." if len(info["desc"]) > 80 else ""),
                    "size": "Small",
                    "isSubtle": True,
                    "wrap": True
                })
            preview_columns.append({
                "type": "Column",
                "width": "stretch",
                "items": col_items
            })

        body.append({
            "type": "ColumnSet",
            "columns": preview_columns,
            "spacing": "Medium"
        })

    # ChoiceSet for socks selection
    body.extend([
        {
            "type": "TextBlock",
            "text": "**Dostupné modely a velikosti:**",
            "wrap": True,
            "spacing": "Medium"
        },
        {
            "type": "Input.ChoiceSet",
            "id": "selected_sock_item",
            "style": "expanded",  # Radio buttons instead of a dropdown
            "isMultiSelect": False,
            "value": choices[0]["value"] if choices else "",
            "choices": choices
        },
        {
            "type": "TextBlock",
            "text": "**Poznámka / Vzkaz (volitelné):**",
            "spacing": "Small",
            "wrap": True
        },
        {
            "type": "Input.Text",
            "id": "order_note",
            "placeholder": "Např. předat v kanceláři 3. patro, barva...",
            "isMultiline": False,
            "maxLength": 200
        }
    ])

    # Card structure
    card = {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.2",
        "body": body,
        "actions": [
            {
                "type": "Action.Submit",
                "title": "✅ OBJEDNAT PONOŽKY",
                "style": "positive",
                "data": {
                    "command": "order_socks"
                }
            }
        ]
    }

    return card


def build_order_confirmation_card(model: str, size: str, person_name: str, note: str = "") -> Dict[str, Any]:
    """Generates an Adaptive Card confirming the successful order."""
    body = [
        {
            "type": "TextBlock",
            "text": "🎉 Objednávka úspěšně přijata!",
            "weight": "Bolder",
            "size": "Large",
            "color": "Good"
        },
        {
            "type": "TextBlock",
            "text": f"Díky **{person_name}**! Tvoje volba byla úspěšně zaznamenána.",
            "wrap": True,
            "spacing": "Small"
        },
        {
            "type": "FactSet",
            "facts": [
                {"title": "Model:", "value": model},
                {"title": "Velikost:", "value": size},
                {"title": "Poznámka:", "value": note if note else "Bez poznámky"}
            ],
            "spacing": "Medium"
        },
        {
            "type": "TextBlock",
            "text": "🧦 Zastav se u Květáka pro vyzvednutí!",
            "weight": "Bolder",
            "spacing": "Medium",
            "wrap": True
        }
    ]

    return {
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "type": "AdaptiveCard",
        "version": "1.2",
        "body": body
    }
