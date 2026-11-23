# Coordinator browser check 2026-11-22 21:47 (local docs/, laptops)
- Works: 2655 rows, search "yoga 7" = 49, configs grouped under model (Yoga 7 2-in-1 14AGP11, MTMs 83TD000US...).
- Data: cpu.model holds raw PSREF string "AMD Ryzen AI 5 430 (4C / 8T, 2.0 / 4.5GHz, 4MB L2 / 8MB L3)" -> split into model + cores/threads/clocks/cache.
- Data: Apple cpu.model = whole chip paragraph; GPU/RAM/storage "Not yet extracted" for Apple models.
- Format: storage "1000 GB" should display as 1 TB (unit display rule).
- UX: default sort Brand asc puts thin Apple model rows first; prefer default sort by completeness or brand=Lenovo-first? (decide: sort by spec coverage desc).
- favicon.ico 404 (trivial).

# 2026-11-23 00:46 monitors check
- Monitors renders 4133 trusted rows, no console errors.
- Preview box copy is laptop-specific ("e.g. Dell, Surface, Apple") on monitors with 0 preview brands: make per-category or hide when 0.
- Size class "Not yet extracted" for ASUS rows: derive from display diagonal spec (derived claim kind).
- SSD/other names contain HTML entities like &trade; -> decode in adapters
