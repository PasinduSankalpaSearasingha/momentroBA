import unittest
from scraper.extractor import (
    extract_deterministic_data,
    clean_email,
    clean_phone,
    extract_contact_links
)
from scraper.models import ContactDetails

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Acme Global Inc - Next Generation Logistics</title>
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@type": "Corporation",
        "name": "Acme Global",
        "email": "hq@acmeglobal.com",
        "telephone": "+1-800-555-0199",
        "address": {
            "@type": "PostalAddress",
            "streetAddress": "100 Innovation Way",
            "addressLocality": "San Francisco",
            "addressRegion": "CA",
            "postalCode": "94107",
            "addressCountry": "USA"
        }
    }
    </script>
</head>
<body>
    <header>
        <a href="/about-us">About Acme</a>
        <a href="/contact">Contact Support</a>
    </header>
    <main>
        <h1>Welcome to Acme Global</h1>
        <p>Feel free to reach our sales team at <a href="mailto:sales@acmeglobal.com">sales@acmeglobal.com</a> or call us at <a href="tel:+14155552673">+1 (415) 555-2673</a>.</p>
        <p>Visit our map: <a href="https://maps.google.com/?q=Acme+Global+San+Francisco">Google Maps Directions</a></p>
    </main>
    <footer>
        <address>
            Acme Global Europe, 25 Baker Street, Marylebone, London W1U 8EJ, United Kingdom
        </address>
        <p>Follow us on <a href="https://www.linkedin.com/company/acme-global">LinkedIn</a> and <a href="https://twitter.com/acmeglobal">Twitter</a></p>
    </footer>
</body>
</html>
"""

class TestExtractor(unittest.TestCase):
    def test_clean_email(self):
        self.assertEqual(clean_email("info@testcompany.com"), "info@testcompany.com")
        self.assertIsNone(clean_email("logo@test.png"))
        self.assertIsNone(clean_email("example@example.com"))

    def test_clean_phone(self):
        self.assertEqual(clean_phone("+1 800-555-0199"), "+1 800-555-0199")
        self.assertIsNone(clean_phone("12345")) # too short

    def test_extract_deterministic_data(self):
        data = extract_deterministic_data(SAMPLE_HTML, "https://acmeglobal.com")
        
        # Test emails
        self.assertIn("hq@acmeglobal.com", data.emails)
        self.assertIn("sales@acmeglobal.com", data.emails)

        # Test phones
        self.assertTrue(any("800-555-0199" in p or "415" in p for p in data.phone_numbers))

        # Test locations
        self.assertGreaterEqual(len(data.locations), 1)
        found_sf = any("San Francisco" in loc.full_address for loc in data.locations)
        self.assertTrue(found_sf)

        # Test social links
        self.assertIn("linkedin", data.social_links)
        self.assertIn("twitter", data.social_links)

        # Test contact subpage discovery
        self.assertIn("https://acmeglobal.com/contact", data.contact_pages_found)
        self.assertIn("https://acmeglobal.com/about-us", data.contact_pages_found)

    def test_topic_and_section_extraction(self):
        from scraper.extractor import extract_page_topics_and_sections, filter_sections_by_ids

        pages = {"https://acmeglobal.com": SAMPLE_HTML}
        topics = extract_page_topics_and_sections(pages)
        self.assertTrue(len(topics) >= 2)
        
        # Verify topics have id, topic name, page_url, content
        for t in topics:
            self.assertIn("id", t)
            self.assertIn("topic", t)
            self.assertIn("page_url", t)
            self.assertIn("content", t)

        topic_names = [t["topic"] for t in topics]
        # Should detect "Welcome to Acme Global" and Footer
        self.assertTrue(any("Welcome to Acme Global" in name for name in topic_names))
        self.assertTrue(any("Footer" in name for name in topic_names))

        # Test filter_sections_by_ids
        first_id = topics[0]["id"]
        filtered_text = filter_sections_by_ids(topics, [first_id])
        self.assertTrue(len(filtered_text) > 0)
        self.assertIn(topics[0]["topic"], filtered_text)

    def test_deduplicate_phone_numbers(self):
        from scraper.extractor import deduplicate_phone_numbers

        # Test formatting variations of the exact same number (e.g. Enfection number)
        raw_numbers = [
            "+94 112 214 4917",
            "+941122144917",
            "01122144917"
        ]
        result = deduplicate_phone_numbers(raw_numbers)
        self.assertEqual(len(result), 1)
        self.assertIn("+94 112 214 4917", result[0])

        # Test different numbers are preserved
        mixed_numbers = [
            "+94 112 214 4917",
            "+941122144917",
            "+1 800-555-0199"
        ]
        result2 = deduplicate_phone_numbers(mixed_numbers)
        self.assertEqual(len(result2), 2)

    def test_deduplicate_locations(self):
        from scraper.extractor import deduplicate_locations
        from scraper.models import LocationInfo

        locs = [
            LocationInfo(label="HQ", full_address="651 Kotte Rd, Kotte, Sri Lanka"),
            LocationInfo(label="Office", full_address="651 Kotte Rd, Kotte")
        ]
        unique = deduplicate_locations(locs)
        self.assertEqual(len(unique), 1)
        # Keeps more comprehensive address
        self.assertEqual(unique[0].full_address, "651 Kotte Rd, Kotte, Sri Lanka")

if __name__ == "__main__":
    unittest.main()
