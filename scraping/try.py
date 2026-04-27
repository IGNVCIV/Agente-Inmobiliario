from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import pandas as pd
import time
import re


def limpiar_texto(texto: str) -> str:
    if not texto:
        return ""
    return " ".join(texto.split())


urls = [
    "https://www.portalinmobiliario.com/MLC-1894972853-departamento-en-venta-de-4-dorm-en-las-condes-_JM",
    "https://www.portalinmobiliario.com/MLC-3779707978-departamento-en-venta-de-2-dorm-en-las-condes-_JM",
    "https://www.portalinmobiliario.com/MLC-2983312172-martin-de-zamora-4464-2-dormitorios-3-banos-2-est-bod-_JM#is_advertising=true&item_id=MLC2983312172&type=pads-lite&ad_placement=SEARCH-VIS-RE_PADSLITE_RESULTS_DESKTOP&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749",
    "https://www.portalinmobiliario.com/MLC-3763938436-malaga-950-4-dorm-3-banos-sin-comision-_JM#is_advertising=true&item_id=MLC3763938436&type=pads-lite&ad_placement=SEARCH-VIS-RE_PADSLITE_RESULTS_DESKTOP&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749",
    "https://www.portalinmobiliario.com/MLC-1895855837-departamento-en-venta-de-4-dorm-en-las-condes-_JM#polycard_client=search-desktop&search_layout=grid&position=2&type=item&float_highlight=recent_publication&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749&price_drop=not_apply",
    "https://www.portalinmobiliario.com/MLC-1893807971-departamento-en-venta-de-3-dorm-en-las-condes-_JM#polycard_client=search-desktop&search_layout=grid&position=3&type=item&float_highlight=recent_publication&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749&price_drop=not_apply",
    "https://www.portalinmobiliario.com/MLC-1897972323-departamento-en-venta-de-1-dorm-en-las-condes-_JM#polycard_client=search-desktop&search_layout=grid&position=5&type=item&float_highlight=recent_publication&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749&price_drop=not_apply",
    "https://www.portalinmobiliario.com/MLC-1505292465-departamento-en-venta-parque-juan-pablo-ii-las-condes-_JM#polycard_client=search-desktop&search_layout=grid&position=7&type=item&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749&price_drop=not_apply",
    "https://www.portalinmobiliario.com/MLC-3745834076-departamento-primer-piso-con-jardin-propio-_JM#polycard_client=search-desktop&search_layout=grid&position=8&type=item&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749&price_drop=not_apply",
    "https://www.portalinmobiliario.com/MLC-1889001261-espectacular-departamento-en-venta-de-2d2b-2es1bd-_JM#polycard_client=search-desktop&search_layout=grid&position=9&type=item&float_highlight=recent_publication&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749&price_drop=not_apply",
    "https://www.portalinmobiliario.com/MLC-3780368130-departamento-en-venta-de-3-dorm-en-las-condes-_JM#polycard_client=search-desktop&search_layout=grid&position=10&type=item&float_highlight=recent_publication&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749&price_drop=not_apply",
    "https://www.portalinmobiliario.com/MLC-1893707547-dpto-de-4-dorm-espectacular-jardin-y-piscina-privada-_JM#polycard_client=search-desktop&search_layout=grid&position=11&type=item&float_highlight=recent_publication&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749&price_drop=not_apply",
    "https://www.portalinmobiliario.com/MLC-1894794369-impecable-estado-gran-vista-despejada-al-nor-oriente-_JM#polycard_client=search-desktop&search_layout=grid&position=12&type=item&float_highlight=recent_publication&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749&price_drop=not_apply",
    "https://www.portalinmobiliario.com/MLC-3772954454-departamento-en-venta-de-4-dorm-en-las-condes-_JM#polycard_client=search-desktop&search_layout=grid&position=13&type=item&float_highlight=recent_publication&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749&price_drop=not_apply",
    "https://www.portalinmobiliario.com/MLC-2898776218-alonso-de-cordova-parque-arauco-_JM#polycard_client=search-desktop&search_layout=grid&position=14&type=item&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749&price_drop=not_apply",
    "https://www.portalinmobiliario.com/MLC-1759562561-dep-renovado-amplio-2-dor2ban-_JM#polycard_client=search-desktop&search_layout=grid&position=15&type=item&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749&price_drop=not_apply",
    "https://www.portalinmobiliario.com/MLC-1855359827-departamento-en-venta-las-condes-_JM#polycard_client=search-desktop&search_layout=grid&position=16&type=item&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749&price_drop=not_apply",
    "https://www.portalinmobiliario.com/MLC-1884982175-departamento-en-venta-de-3-dorm-en-las-condes-_JM#polycard_client=search-desktop&search_layout=grid&position=18&type=item&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749&price_drop=not_apply",
    "https://www.portalinmobiliario.com/MLC-3763991976-espectacular-depto-vista-club-de-golf-los-leones-_JM#polycard_client=search-desktop&search_layout=grid&position=19&type=item&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749&price_drop=not_apply",
    "https://www.portalinmobiliario.com/MLC-1885485677-luminoso-depto-4-dormitorios-3-banos-y-espectacular-vista-_JM#polycard_client=search-desktop&search_layout=grid&position=20&type=item&tracking_id=2a27da5b-7820-4a20-a79a-04fd68f8e749&price_drop=not_apply"
]

options = Options()
options.add_argument("--start-maximized")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 15)

resultados = []

try:
    for url in urls:
        print(f"Procesando: {url}")

        driver.get(url)
        wait.until(EC.presence_of_element_located(("tag name", "body")))
        time.sleep(3)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # ===== TITULO =====
        titulo = None
        titulo_tag = soup.select_one("h1.ui-pdp-title") or soup.select_one("h1")
        if titulo_tag:
            titulo = limpiar_texto(titulo_tag.get_text())

        # ===== PRECIO =====
        precio = None
        precio_tag = (
            soup.select_one(".ui-pdp-price__second-line .andes-money-amount__fraction")
            or soup.select_one(".andes-money-amount__fraction")
        )
        if precio_tag:
            precio = limpiar_texto(precio_tag.get_text())

        # ===== UBICACION =====
        ubicacion = None
        candidatos_ubicacion = soup.select(
            'a[href*="map"], a[href*="/propiedades/"], div.ui-vip-location__subtitle'
        )

        for tag in candidatos_ubicacion:
            texto = limpiar_texto(tag.get_text())
            texto_lower = texto.lower()

            if not texto:
                continue
            if "contraseñas" in texto_lower or "whatsapp" in texto_lower or "verificación" in texto_lower:
                continue
            if len(texto) < 5:
                continue

            ubicacion = texto
            break

        # ===== TEXTO GENERAL =====
        texto_completo = limpiar_texto(soup.get_text(" ", strip=True)).lower()

        dormitorios = None
        banos = None
        metros = None

        dorm_match = re.search(r"(\d+)\s*dorm", texto_completo)
        if dorm_match:
            dormitorios = dorm_match.group(1)

        banos_match = re.search(r"(\d+)\s*bañ", texto_completo)
        if banos_match:
            banos = banos_match.group(1)

        metros_match = re.search(r"(\d+[.,]?\d*)\s*m²", texto_completo)
        if metros_match:
            metros = metros_match.group(1)

        resultado = {
            "titulo": titulo,
            "precio": precio,
            "ubicacion": ubicacion,
            "dormitorios": dormitorios,
            "banos": banos,
            "metros": metros,
            "link": url,
        }

        resultados.append(resultado)

    df = pd.DataFrame(resultados)
    print(df)
    df.to_csv("propiedades_portalinmobiliario_detalle.csv", index=False, encoding="utf-8-sig")
    print("\nArchivo guardado: propiedades_portalinmobiliario_detalle.csv")

finally:
    driver.quit()