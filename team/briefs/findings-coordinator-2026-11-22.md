# Coordinator browser check 2026-11-22 21:47 (local docs/, laptops)
- Works: 2655 rows, search "yoga 7" = 49, configs grouped under model (Yoga 7 2-in-1 14AGP11, MTMs 83TD000US...).
- Data: cpu.model holds raw PSREF string "AMD Ryzen AI 5 430 (4C / 8T, 2.0 / 4.5GHz, 4MB L2 / 8MB L3)" -> split into model + cores/threads/clocks/cache.
- Data: Apple cpu.model = whole chip paragraph; GPU/RAM/storage "Not yet extracted" for Apple models.
- Format: storage "1000 GB" should display as 1 TB (unit display rule).
- UX: default sort Brand asc puts thin Apple model rows first; prefer default sort by completeness or brand=Lenovo-first? (decide: sort by spec coverage desc).
- favicon.ico 404 (trivial).
