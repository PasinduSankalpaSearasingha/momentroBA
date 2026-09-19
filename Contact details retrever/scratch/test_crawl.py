import scrapy
from scrapy.crawler import CrawlerProcess

class MySpider(scrapy.Spider):
    name = "test"
    start_urls = ["https://httpbin.org/html"]

    def parse(self, response):
        print(">>> GOT RESPONSE:", response.status, len(response.text))

process = CrawlerProcess({
    "LOG_LEVEL": "DEBUG",
    "TELNETCONSOLE_ENABLED": False,
    "REQUEST_FINGERPRINTER_IMPLEMENTATION": "2.7",
})
process.crawl(MySpider)
process.start()
