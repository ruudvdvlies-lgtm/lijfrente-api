@echo off
echo ==========================
echo Lijfrente data updaten...
echo ==========================

cd /d "G:\Mijn Drive\_1 organisaties\_Weadvize\_WeAdvize\Lijfrenteinzicht\mnt\data\lijfrente_scraper"

echo Stap 1: scraping draaien
python scrape_lijfrente.py

echo Stap 2: kopie naar API map
copy "scraped_rates.csv" "G:\Mijn Drive\_1 organisaties\_Weadvize\_WeAdvize\Lijfrenteinzicht\lijfrente-api\scraped_rates.csv" /Y
cd /d "G:\Mijn Drive\_1 organisaties\_Weadvize\_WeAdvize\Lijfrenteinzicht\lijfrente-api"

echo Stap 3: Git update
git add .
git commit -m "daily update"
git push

echo ==========================
echo Klaar! API wordt geupdate 🚀
echo ==========================

pause