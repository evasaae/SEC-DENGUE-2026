# SIGAP-DBD

## Struktur Folder
SEC-DENGUE-2026/
├── .github/
│   └── workflows/
│       └── scrape.yml        # GitHub actions
├── data/
│   ├── berita_dbd.csv        # Volume berita DBD per kabupaten 
│   ├── detail_berita.csv     # Judul, link, dan sumber berita terbaru
│   └── last_updated.txt      # Timestamp update data terakhir
├── web-scrapping/
│   └── scrap.py              # Script scraping RSS 
├── volberita.py              # Naive Bayes model in progress
└── README.md
