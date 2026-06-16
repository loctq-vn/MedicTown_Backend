from app.services import recommendation_service


def test_rank_products_prefers_purchase_affinity_and_excludes_recent_purchase():
    context = recommendation_service.RecommendationContext(
        purchase_products=[
            {
                "id": "purchased-product",
                "subcategory_id": "pain-relief",
                "brand": "Brand A",
                "manufacturer": "Maker A",
                "shop_id": "shop-1",
            }
        ],
        add_to_cart_products=[],
        view_products=[],
    )
    candidates = [
        {
            "id": "recently-purchased",
            "subcategory_id": "pain-relief",
            "brand": "Brand A",
            "manufacturer": "Maker A",
            "shop_id": "shop-1",
            "stock": 10,
            "is_active": True,
        },
        {
            "id": "similar-product",
            "subcategory_id": "pain-relief",
            "brand": "Brand B",
            "manufacturer": "Maker B",
            "shop_id": "shop-2",
            "stock": 10,
            "is_active": True,
        },
        {
            "id": "popular-product",
            "subcategory_id": "vitamin",
            "brand": "Other",
            "manufacturer": "Other",
            "shop_id": "shop-3",
            "stock": 10,
            "is_active": True,
        },
    ]

    ranked = recommendation_service._rank_products(
        candidates=candidates,
        context=context,
        best_seller_scores={"popular-product": 1},
        rating_scores={"popular-product": 1},
        exclude_product_ids={"recently-purchased"},
        limit=10,
    )

    assert [product["id"] for product in ranked] == [
        "similar-product",
        "popular-product",
    ]
    assert ranked[0]["recommendation_score"] > ranked[1]["recommendation_score"]
    assert "purchase_match" in ranked[0]["recommendation_reasons"]
    assert "same_subcategory" in ranked[0]["recommendation_reasons"]


def test_rank_products_skips_inactive_and_out_of_stock_candidates():
    context = recommendation_service.RecommendationContext(
        purchase_products=[],
        add_to_cart_products=[],
        view_products=[
            {
                "id": "viewed-product",
                "subcategory_id": "skin-care",
                "brand": "Brand A",
                "manufacturer": "Maker A",
                "shop_id": "shop-1",
            }
        ],
    )
    candidates = [
        {
            "id": "inactive-product",
            "subcategory_id": "skin-care",
            "stock": 10,
            "is_active": False,
        },
        {
            "id": "out-of-stock-product",
            "subcategory_id": "skin-care",
            "stock": 0,
            "is_active": True,
        },
        {
            "id": "available-product",
            "subcategory_id": "skin-care",
            "brand": "Brand A",
            "manufacturer": "Maker A",
            "shop_id": "shop-1",
            "stock": 5,
            "is_active": True,
        },
    ]

    ranked = recommendation_service._rank_products(
        candidates=candidates,
        context=context,
        best_seller_scores={},
        rating_scores={},
        exclude_product_ids=set(),
        limit=10,
    )

    assert [product["id"] for product in ranked] == ["available-product"]
    assert "view_match" in ranked[0]["recommendation_reasons"]
