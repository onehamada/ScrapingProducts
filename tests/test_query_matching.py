import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from marketplace_scraper import (
    AliExpressScraper,
    ArtifactStore,
    build_error_report,
    build_market_insights,
    build_search_candidates,
    ChromeFactory,
    determine_search_target_count,
    evaluate_title_reason,
    FacebookMarketplaceScraper,
    Listing,
    MercadoLivreScraper,
    MarketplaceService,
    OLXScraper,
    resolve_category,
    SearchCache,
    title_contains_query,
)
from selenium.common.exceptions import WebDriverException


class QueryMatchingTests(unittest.TestCase):
    def test_marketplace_service_registers_all_expected_platforms(self) -> None:
        self.assertEqual(
            MarketplaceService().available_platforms(),
            [
                "olx",
                "mercadolivre",
                "kabum",
                "terabyte",
                "pcgamerbrasilia",
                "aliexpress",
                "facebook",
            ],
        )

    def test_error_report_persists_each_platform_outcome(self) -> None:
        results = {
            "olx": {
                "success": True,
                "count": 2,
                "scanned_count": 6,
                "items": [],
            },
            "mercadolivre": {
                "success": False,
                "count": 0,
                "error": "Verificacao de seguranca",
                "items": [],
            },
            "facebook": {
                "success": True,
                "count": 0,
                "note": "Nenhum anuncio retornado.",
                "items": [],
            },
        }
        report = build_error_report("rx 580", list(results), results)

        self.assertEqual(
            report["summary"],
            {"platforms": 3, "ok": 1, "no_results": 1, "failed": 1, "issues": 2},
        )
        self.assertEqual(report["results"]["mercadolivre"]["status"], "failed")
        self.assertEqual(report["results"]["facebook"]["status"], "no_results")
        self.assertEqual(len(report["issues"]), 2)

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("marketplace_scraper.ARTIFACTS_JSON_DIR", Path(temp_dir)):
                artifact_path = ArtifactStore().save_error_report("rx 580", report)
            saved_report = json.loads(
                (Path(temp_dir) / Path(artifact_path).name).read_text(encoding="utf-8")
            )

        self.assertEqual(saved_report, report)
        self.assertTrue(artifact_path.startswith("/artifacts/json/"))

    def test_search_many_generates_one_error_report_for_the_search(self) -> None:
        service = MarketplaceService()
        platform_result = {
            "source": "olx",
            "success": True,
            "count": 0,
            "items": [],
            "error": "",
            "note": "Nenhum item retornado.",
        }

        with (
            patch.object(service, "search_platform", return_value=platform_result) as search_mock,
            patch.object(service.artifacts, "save_error_report", return_value="/artifacts/json/report.json") as report_mock,
            patch.object(service.artifacts, "save_json", return_value=""),
        ):
            payload = service.search_many("rx 580", ["olx"])

        self.assertEqual(payload["error_report"], "/artifacts/json/report.json")
        self.assertEqual(search_mock.call_count, 1)
        self.assertFalse(search_mock.call_args.kwargs["_generate_error_report"])
        self.assertEqual(report_mock.call_count, 1)
        self.assertEqual(report_mock.call_args.args[1]["summary"]["no_results"], 1)

    def test_facebook_public_listing_does_not_require_login(self) -> None:
        scraper = FacebookMarketplaceScraper(ChromeFactory(), ArtifactStore())
        page_html = (
            '<form><input name="email"></form>'
            '<a href="/marketplace/item/123/">RTX 3060 R$ 2.000</a>'
        )

        self.assertFalse(
            scraper._needs_login(
                page_html,
                "https://www.facebook.com/marketplace/saopaulo/search/?query=rtx",
            )
        )

    def test_mercadolivre_account_verification_is_reported_as_error(self) -> None:
        scraper = MercadoLivreScraper(ChromeFactory(), ArtifactStore())

        error = scraper.detect_error(
            "Mercado Libre",
            '<html><body><main class="suspicious-traffic-frontend"></main></body></html>',
            "https://www.mercadolivre.com.br/gz/account-verification?go=%2Frx-580",
        )

        self.assertIn("verificacao de seguranca", error)

    def test_monitor_query_matches_titles_with_double_quote_inches(self) -> None:
        title = 'Monitor Gamer LG 24" Full HD, 100Hz, IPS, 5ms'
        self.assertTrue(title_contains_query("monitor 24 polegadas", title))

    def test_monitor_query_matches_titles_with_pol_inches(self) -> None:
        title = "Monitor Gamer 24 Pol, Full HD, 1ms, 180Hz, IPS"
        self.assertTrue(title_contains_query("monitor 24 polegadas", title))

    def test_monitor_query_accepts_238_as_24_inch_class(self) -> None:
        title = "Monitor Gamer AOC, 23.8 Pol, Full HD, VA, LED, 1ms, 100Hz"
        self.assertTrue(title_contains_query("monitor 24 polegadas", title))

    def test_monitor_numeric_token_does_not_match_substring(self) -> None:
        title = (
            "Monitor Gamer Samsung Odyssey G40 27 Full HD, IPS, 240Hz, 1ms, "
            "FreeSync Premium"
        )
        self.assertFalse(title_contains_query("monitor 24", title))

    def test_monitor_query_does_not_use_model_code_as_size_match(self) -> None:
        title = "Monitor Gamer X, 27 Pol, IPS, HDMI, Modelo 24B30HM2"
        self.assertFalse(title_contains_query("monitor 24 polegadas", title))

    def test_display_size_query_adds_stripped_fallback(self) -> None:
        candidates = build_search_candidates("monitor 24 polegadas")
        self.assertIn("monitor 24", candidates)

    def test_gpu_query_stays_strict_for_other_model(self) -> None:
        title = "Placa de Video GTX 1070 8GB GDDR5"
        self.assertFalse(title_contains_query("gtx 1060", title))

    def test_motherboard_query_matches_title_without_literal_placa_mae(self) -> None:
        title = "ASUS Prime B550M-A DDR4 AM4"
        self.assertTrue(title_contains_query("placa mae b550m", title))

    def test_memory_query_matches_title_without_literal_memoria_ram(self) -> None:
        title = "Kingston Fury Beast 16GB DDR4 3200MHz"
        self.assertTrue(title_contains_query("memoria ram 16gb ddr4", title))

    def test_power_supply_query_matches_psu_title(self) -> None:
        title = "Corsair CV650 650W 80 Plus Bronze PSU"
        self.assertTrue(title_contains_query("fonte 650w", title))

    def test_search_candidates_add_motherboard_fallback_without_generic_term(self) -> None:
        candidates = build_search_candidates("placa mae b550m")
        self.assertIn("b550m", candidates)

    def test_resolve_category_detects_hardware_profiles(self) -> None:
        self.assertEqual(resolve_category("placa mae b550m aorus", "auto"), "placa-mae")
        self.assertEqual(resolve_category("memoria ram ddr4 16gb 3200mhz", "auto"), "memoria")
        self.assertEqual(resolve_category("ssd notebook 512gb nvme", "auto"), "armazenamento")
        self.assertEqual(resolve_category("fonte 650w 80 plus bronze", "auto"), "fonte")
        self.assertEqual(resolve_category("gabinete branco mid tower", "auto"), "gabinete")
        self.assertEqual(resolve_category("water cooler 240mm am4", "auto"), "cooler")

    def test_motherboard_bundle_listing_is_rejected_when_query_is_board_only(self) -> None:
        title = "Kit Upgrade Ryzen 5600 + B550M + 16GB DDR4"
        self.assertEqual(
            evaluate_title_reason("placa mae b550m", title, "placa-mae"),
            "bundle_term",
        )

    def test_search_cache_returns_isolated_nested_payloads(self) -> None:
        cache = SearchCache(ttl_seconds=60, max_entries=4)
        key = ("olx", "gtx 1060", "auto", 8, False)
        payload = {
            "source": "olx",
            "success": True,
            "items": [
                {
                    "title": "GTX 1060 6GB",
                    "price": "R$ 900",
                    "comparison_adjustment": {"kind": "import_tax", "tax_value": 90.0},
                    "deal": {"tone": "good", "score": 20},
                }
            ],
            "stats": {"discarded_reasons": {"query_mismatch": 1}},
            "search_attempts": [{"search_term": "gtx 1060", "count": 1, "success": True}],
            "search_terms_used": ["gtx 1060"],
        }

        cache.set(key, payload)
        cached = cache.get(key)
        self.assertIsNotNone(cached)
        assert cached is not None

        cached["items"][0]["title"] = "alterado"
        cached["items"][0]["comparison_adjustment"]["tax_value"] = 999.0
        cached["items"][0]["deal"]["score"] = -1
        cached["stats"]["discarded_reasons"]["query_mismatch"] = 99
        cached["search_attempts"][0]["count"] = 5
        cached["search_terms_used"].append("extra")

        fresh = cache.get(key)
        self.assertEqual(fresh["items"][0]["title"], "GTX 1060 6GB")
        self.assertEqual(fresh["items"][0]["comparison_adjustment"]["tax_value"], 90.0)
        self.assertEqual(fresh["items"][0]["deal"]["score"], 20)
        self.assertEqual(fresh["stats"]["discarded_reasons"]["query_mismatch"], 1)
        self.assertEqual(fresh["search_attempts"][0]["count"], 1)
        self.assertEqual(fresh["search_terms_used"], ["gtx 1060"])
        self.assertEqual(payload["items"][0]["title"], "GTX 1060 6GB")
        self.assertEqual(payload["items"][0]["comparison_adjustment"]["tax_value"], 90.0)
        self.assertEqual(payload["items"][0]["deal"]["score"], 20)

    def test_market_insights_use_comparison_price_for_imported_items(self) -> None:
        results = {
            "olx": {
                "items": [
                    {
                        "title": "Placa de Video RTX 4060",
                        "price": "R$ 1.200",
                        "price_value": 1200.0,
                        "url": "https://example.com/local",
                    }
                ]
            },
            "aliexpress": {
                "items": [
                    {
                        "title": "RTX 4060 Importada",
                        "price": "R$ 900",
                        "price_value": 900.0,
                        "comparison_price": "R$ 1.700",
                        "comparison_price_value": 1700.0,
                        "comparison_adjustment": {"kind": "import_tax_estimate"},
                        "url": "https://example.com/imported",
                    }
                ]
            },
        }

        insights = build_market_insights(results)

        self.assertEqual(insights["priced_items"], 2)
        self.assertEqual(insights["cheapest_item"]["url"], "https://example.com/local")
        self.assertIn("custo final", insights["summary_note"])

    def test_aliexpress_detail_tax_parser_handles_inline_markup(self) -> None:
        scraper = AliExpressScraper(ChromeFactory(), ArtifactStore())
        html = "<div><span>R$ 123,45</span><span> em impostos estimados</span></div>"

        tax_percent, tax_value, tax_label = scraper._extract_import_tax_from_detail_html(
            html,
            1000.0,
        )

        self.assertEqual(tax_value, 123.45)
        self.assertEqual(tax_percent, 12.3)
        self.assertIn("R$ 123,45", tax_label)

    def test_aliexpress_post_process_uses_cached_tax_before_opening_driver(self) -> None:
        scraper = AliExpressScraper(ChromeFactory(), ArtifactStore())
        item = Listing(
            source="aliexpress",
            title="RTX 4060 Importada",
            price="R$ 900",
            price_value=900.0,
            url="https://pt.aliexpress.com/item/123.html",
            shipping_origin="Importado de China",
            shipping_origin_code="CN",
            is_imported=True,
        )
        scraper._set_cached_detail_tax(item.url, 20.0, 180.0, "R$ 180,00 estimados (20%)")

        with patch.object(scraper, "_create_detail_tax_driver") as create_driver_mock:
            processed = scraper.post_process_items([item], headless=True)

        self.assertEqual(len(processed), 1)
        self.assertEqual(processed[0].import_tax_value, 180.0)
        self.assertEqual(processed[0].import_tax_percent, 20.0)
        self.assertEqual(processed[0].import_tax_label, "R$ 180,00 estimados (20%)")
        self.assertIsNotNone(processed[0].comparison_price_value)
        create_driver_mock.assert_not_called()

    def test_olx_parser_reads_items_from_next_data_payload(self) -> None:
        scraper = OLXScraper(ChromeFactory(), ArtifactStore())
        payload = {
            "props": {
                "pageProps": {
                    "ads": [
                        {
                            "subject": "PLACA DE VIDEO RX 590 8GB (NOVA COM GARANTIA)",
                            "priceValue": "R$ 799",
                            "friendlyUrl": "/distrito-federal-e-regiao/informatica/placas-de-video/rx-590-123",
                            "location": "Brasilia - DF",
                            "date": 1774704482,
                            "categoryName": "Placas de Video",
                            "images": [
                                {
                                    "originalWebp": "https://img.example/rx590.webp",
                                }
                            ],
                            "olxPay": {
                                "transactionalBadges": [
                                    {"text": "Entrega Facil"},
                                    {"text": "Pague Online"},
                                    {"text": "Parcelamento sem juros"},
                                ],
                                "installments": [
                                    {
                                        "times": 3,
                                        "highlighted": True,
                                        "price": {"label": "R$ 266,33"},
                                        "fee": {"raw": 0},
                                    }
                                ],
                            },
                            "properties": [
                                {"label": "Modelo", "value": "Radeon RX"},
                                {"label": "Memoria de Video - VRAM", "value": "8 GB"},
                            ],
                        }
                    ]
                }
            }
        }
        html = (
            "<html><body><script id=\"__NEXT_DATA__\" type=\"application/json\">"
            f"{json.dumps(payload)}"
            "</script></body></html>"
        )

        items = scraper.parse_items(html, 5)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "PLACA DE VIDEO RX 590 8GB (NOVA COM GARANTIA)")
        self.assertEqual(items[0].price, "R$ 799")
        self.assertEqual(items[0].price_value, 799.0)
        self.assertEqual(
            items[0].url,
            "https://www.olx.com.br/distrito-federal-e-regiao/informatica/placas-de-video/rx-590-123",
        )
        self.assertEqual(items[0].image, "https://img.example/rx590.webp")
        self.assertIn("Entrega Facil", items[0].shipping)
        self.assertEqual(items[0].installment, "3x de R$ 266,33 sem juros")
        self.assertIn("Modelo: Radeon RX", items[0].raw_text)

    def test_olx_parser_reads_cards_with_multiple_css_classes(self) -> None:
        scraper = OLXScraper(ChromeFactory(), ArtifactStore())
        html = """
            <section class="olx-adcard olx-adcard__horizontal undefined">
                <a data-testid="adcard-link" href="https://www.olx.com.br/informatica/placas/rx-580-123"
                   title="RX 580 8GB">RX 580 8GB</a>
                <h3 class="olx-adcard__price font-semibold">R$ 449</h3>
            </section>
        """

        items = scraper.parse_items(html, 5)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "RX 580 8GB")
        self.assertEqual(items[0].price, "R$ 449")
        self.assertEqual(items[0].price_value, 449.0)
        self.assertEqual(
            items[0].url,
            "https://www.olx.com.br/informatica/placas/rx-580-123",
        )

    def test_chrome_profile_cleanup_runs_only_once_per_start_cycle(self) -> None:
        factory = ChromeFactory()

        with patch.object(factory, "_preferred_binaries", return_value=(None,)), \
             patch("marketplace_scraper.webdriver.Chrome", side_effect=WebDriverException("chrome failed to start")), \
             patch.object(factory, "_cleanup_persistent_profile") as cleanup_mock, \
             patch("marketplace_scraper.time.sleep"):
            with self.assertRaises(WebDriverException):
                factory._build_driver("test-profile", headless=False, persistent_profile=True)

        self.assertEqual(cleanup_mock.call_count, 1)

    def test_catalog_platforms_stop_after_first_match(self) -> None:
        self.assertEqual(
            determine_search_target_count("kabum", max_results=10, resolved_category="placa-de-video"),
            1,
        )
        self.assertEqual(
            determine_search_target_count("terabyte", max_results=10, resolved_category="auto"),
            1,
        )

    def test_non_catalog_platforms_keep_category_target(self) -> None:
        self.assertEqual(
            determine_search_target_count("olx", max_results=10, resolved_category="auto"),
            2,
        )
        self.assertEqual(
            determine_search_target_count("olx", max_results=10, resolved_category="processador"),
            3,
        )


if __name__ == "__main__":
    unittest.main()
