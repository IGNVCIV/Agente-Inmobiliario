from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import pandas as pd
import time
import re


# =========================
# UTILIDADES
# =========================

def limpiar_texto(texto: str) -> str:
    if not texto:
        return ""
    return " ".join(str(texto).split())


def limpiar_link(url: str):
    if not url:
        return None
    return url.split("#")[0].split("?")[0].strip()


def extraer_id_fuente(url: str):
    if not url:
        return None

    m = re.search(r"(MLC-?\d+)", url, re.IGNORECASE)
    if not m:
        return None

    valor = m.group(1).upper().replace("MLC", "MLC-")
    valor = valor.replace("--", "-")
    return valor


def normalizar_numero(texto: str):
    if texto is None:
        return None

    texto = limpiar_texto(str(texto))

    # 12.500 -> 12500
    if "." in texto and "," not in texto:
        try:
            return int(texto.replace(".", ""))
        except ValueError:
            pass

    # 129,5 -> 129.5
    if "," in texto and "." not in texto:
        try:
            return float(texto.replace(",", "."))
        except ValueError:
            pass

    # 1.234,56 -> 1234.56
    if "." in texto and "," in texto:
        try:
            return float(texto.replace(".", "").replace(",", "."))
        except ValueError:
            pass

    try:
        return int(texto)
    except ValueError:
        pass

    try:
        return float(texto)
    except ValueError:
        return None


# =========================
# EXTRACCIÓN DE CAMPOS
# =========================

def extraer_titulo(soup: BeautifulSoup):
    tag = soup.select_one("h1.ui-pdp-title") or soup.select_one("h1")
    return limpiar_texto(tag.get_text()) if tag else None


def extraer_precio(soup: BeautifulSoup):
    entero = (
        soup.select_one(".ui-pdp-price__second-line .andes-money-amount__fraction")
        or soup.select_one(".andes-money-amount__fraction")
    )
    simbolo = (
        soup.select_one(".ui-pdp-price__second-line .andes-money-amount__currency-symbol")
        or soup.select_one(".andes-money-amount__currency-symbol")
    )

    if not entero:
        return None, None

    precio_texto = limpiar_texto(entero.get_text())
    moneda = limpiar_texto(simbolo.get_text()) if simbolo else None
    precio_valor = normalizar_numero(precio_texto)

    return moneda, precio_valor


def extraer_ubicacion(soup: BeautifulSoup):
    candidatos = soup.select(
        'div.ui-vip-location__subtitle, a[href*="map"], div[class*="location"]'
    )

    bloqueos = [
        "contraseñas",
        "whatsapp",
        "verificación",
        "verificacion",
        "tienda oficial",
        "responde sus consultas",
    ]

    for tag in candidatos:
        texto = limpiar_texto(tag.get_text())
        texto_lower = texto.lower()

        if not texto:
            continue
        if len(texto) < 5:
            continue
        if any(b in texto_lower for b in bloqueos):
            continue

        return texto

    return None


def extraer_comuna(ubicacion: str):
    if not ubicacion:
        return None

    comunas = [
        "las condes",
        "vitacura",
        "providencia",
        "ñuñoa",
        "nunoa",
        "santiago",
        "la reina",
        "lo barnechea",
        "macul",
        "san miguel",
        "estacion central",
        "estación central",
        "independencia",
        "recoleta",
        "peñalolén",
        "penalolen",
    ]

    texto = ubicacion.lower()
    for comuna in comunas:
        if comuna in texto:
            return comuna.title()

    return None


def extraer_texto_completo(soup: BeautifulSoup):
    return limpiar_texto(soup.get_text(" ", strip=True)).lower()


def buscar_patron(texto: str, patrones: list):
    if not texto:
        return None

    for patron in patrones:
        m = re.search(patron, texto, re.IGNORECASE)
        if m:
            valor = m.group(1)
            numero = normalizar_numero(valor)
            return numero

    return None


def extraer_dormitorios(texto: str):
    patrones = [
        r"(\d+)\s*dormitorios?",
        r"(\d+)\s*dorm\b",
        r"(\d+)\s*dor\b",
        r"(\d+)d\b",
    ]
    return buscar_patron(texto, patrones)


def extraer_banos(texto: str):
    patrones = [
        r"(\d+)\s*baños?",
        r"(\d+)\s*banos?",
        r"(\d+)\s*b\b",
        r"(\d+)b\b",
    ]
    return buscar_patron(texto, patrones)


def extraer_metros(texto: str):
    patrones = [
        r"(\d+[.,]?\d*)\s*m²",
        r"(\d+[.,]?\d*)\s*mt2",
        r"(\d+[.,]?\d*)\s*m2\b",
        r"(\d+[.,]?\d*)\s*metros\b",
    ]
    return buscar_patron(texto, patrones)


def extraer_descripcion(soup: BeautifulSoup):
    posibles = [
        "div.ui-pdp-description__content",
        "div[class*='description']",
        "p[class*='description']",
    ]

    bloqueos = [
        "whatsapp",
        "responde sus consultas",
        "tuviste un problema con la publicación",
        "tuviste un problema con la publicacion",
        "avísanos",
        "avisanos",
        "solicitar visita",
        "tienda oficial",
    ]

    for selector in posibles:
        tag = soup.select_one(selector)
        if tag:
            texto = limpiar_texto(tag.get_text(" ", strip=True))
            texto_lower = texto.lower()

            if len(texto) <= 30:
                continue
            if any(b in texto_lower for b in bloqueos):
                continue

            return texto

    return None


def extraer_amenities(soup: BeautifulSoup):
    texto = limpiar_texto(soup.get_text(" ", strip=True)).lower()

    lista = []

    mapa = {
        "piscina": ["piscina"],
        "gimnasio": ["gimnasio", "gym"],
        "quincho": ["quincho"],
        "estacionamiento": ["estacionamiento", "parking"],
        "bodega": ["bodega"],
        "ascensor": ["ascensor"],
        "conserjeria": ["conserjería", "conserjeria"],
        "seguridad": ["seguridad", "vigilancia"],
        "terraza": ["terraza"],
        "jardin": ["jardín", "jardin"],
    }

    for amenity, palabras in mapa.items():
        if any(p in texto for p in palabras):
            lista.append(amenity)

    return ", ".join(lista) if lista else None


# =========================
# EXTRACCIÓN POR URL
# =========================

def extraer_propiedad(driver, wait, url: str):
    url_limpia = limpiar_link(url)
    id_fuente = extraer_id_fuente(url_limpia)

    print(f"Procesando: {url_limpia}")
    driver.get(url_limpia)

    wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "h1, .ui-pdp-title"))
    )
    time.sleep(2)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    titulo = extraer_titulo(soup) or ""
    descripcion = extraer_descripcion(soup) or ""
    ubicacion_raw = extraer_ubicacion(soup)
    comuna = extraer_comuna(ubicacion_raw)

    texto_fuente = f"{titulo} {descripcion}".lower()
    texto_completo = extraer_texto_completo(soup)

    dormitorios = extraer_dormitorios(texto_fuente)
    if dormitorios is None:
        dormitorios = extraer_dormitorios(texto_completo)

    banos = extraer_banos(texto_fuente)
    if banos is None:
        banos = extraer_banos(texto_completo)

    metros = extraer_metros(texto_fuente)
    if metros is None:
        metros = extraer_metros(texto_completo)

    moneda, precio_valor = extraer_precio(soup)

    resultado = {
        "id_fuente": id_fuente,
        "titulo": titulo if titulo else None,
        "moneda": moneda,
        "precio_valor": precio_valor,
        "ubicacion_raw": ubicacion_raw,
        "comuna": comuna,
        "dormitorios": dormitorios,
        "banos": banos,
        "metros": metros,
        "descripcion": descripcion if descripcion else None,
        "amenities": extraer_amenities(soup),
        "link": url_limpia,
        "error": None,
    }

    return resultado


# =========================
# LEER CSV DE LINKS
# =========================

df_links = pd.read_csv("links_propiedades.csv")
df_links.columns = df_links.columns.str.strip().str.lower()

if "link" in df_links.columns:
    urls = df_links["link"].dropna().astype(str).tolist()
elif "url" in df_links.columns:
    urls = df_links["url"].dropna().astype(str).tolist()
else:
    raise ValueError(
        f"No se encontró una columna válida en links_propiedades.csv. "
        f"Columnas detectadas: {list(df_links.columns)}"
    )


# =========================
# SELENIUM
# =========================

options = Options()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--no-sandbox")
# options.add_argument("--headless=new")

driver = webdriver.Chrome(options=options)
wait = WebDriverWait(driver, 15)

resultados = []

try:
    for i, url in enumerate(urls, start=1):
        try:
            print(f"\n[{i}/{len(urls)}]")
            resultado = extraer_propiedad(driver, wait, url)
            resultados.append(resultado)

            if i % 10 == 0:
                df_parcial = pd.DataFrame(resultados)
                df_parcial = df_parcial.drop_duplicates(subset=["id_fuente", "link"]).reset_index(drop=True)
                df_parcial.insert(0, "id", range(1, len(df_parcial) + 1))
                df_parcial.to_csv(
                    "propiedades_detalle_parcial.csv",
                    index=False,
                    encoding="utf-8-sig"
                )
                print("Guardado parcial realizado.")

        except Exception as e:
            url_limpia = limpiar_link(url)
            print(f"Error en {url_limpia}: {e}")

            resultados.append({
                "id_fuente": extraer_id_fuente(url_limpia),
                "titulo": None,
                "moneda": None,
                "precio_valor": None,
                "ubicacion_raw": None,
                "comuna": None,
                "dormitorios": None,
                "banos": None,
                "metros": None,
                "descripcion": None,
                "amenities": None,
                "link": url_limpia,
                "error": str(e),
            })

    df = pd.DataFrame(resultados)
    df = df.drop_duplicates(subset=["id_fuente", "link"]).reset_index(drop=True)
    df.insert(0, "id", range(1, len(df) + 1))

    df.to_csv("propiedades_detalle.csv", index=False, encoding="utf-8-sig")
    print("\nArchivo guardado: propiedades_detalle.csv")

finally:
    driver.quit()