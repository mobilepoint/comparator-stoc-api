import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from datetime import datetime
import time
import json

# Configurare pagină
st.set_page_config(
    page_title="Verificare Stoc SmartBill vs WooCommerce",
    page_icon="📦",
    layout="wide"
)

st.title("📦 Verificare Stoc: SmartBill vs WooCommerce")
st.markdown("---")

# ==================== CONSTANTE ====================
WAREHOUSE_NAME = "Eroilor 19 cv"
WAREHOUSE_TYPE = "en gros"  # cantitativ valorica

# ==================== FUNCȚII DE TEST ====================

def test_smartbill_connection(email, token, cif):
    """Test complet pentru conexiunea SmartBill"""
    st.subheader("🧪 Test Conexiune SmartBill")
    
    try:
        url = "https://ws.smartbill.ro/SBORO/api/stocks"
        
        headers = {
            "Content-Type": "application/xml",
            "Accept": "application/json"
        }
        
        auth = HTTPBasicAuth(email, token)
        
        # Request cu gestiunea specifică
        params = {
            "cif": cif,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "warehouseName": WAREHOUSE_NAME
        }
        
        st.info(f"🔍 Testing endpoint: {url}")
        st.code(f"""Request Details:
CIF: {cif}
Date: {params['date']}
Warehouse: {WAREHOUSE_NAME}
Auth: {email}
""", language="text")
        
        response = requests.get(
            url,
            auth=auth,
            headers=headers,
            params=params,
            timeout=30
        )
        
        st.write(f"**Status Code**: `{response.status_code}`")
        
        if response.status_code == 200:
            st.success("✅ Conexiune reușită!")
            
            try:
                data = response.json()
                
                # Afișează structura completă
                with st.expander("📄 Răspuns JSON complet (primele 500 caractere)"):
                    st.code(json.dumps(data, indent=2, ensure_ascii=False)[:500], language="json")
                
                # Analizează structura
                products = []
                if isinstance(data, list):
                    products = data
                    st.info(f"📦 **Format**: Listă directă cu {len(products)} produse")
                elif isinstance(data, dict):
                    if 'products' in data:
                        products = data['products']
                        st.info(f"📦 **Format**: Obiect cu cheie 'products' - {len(products)} produse")
                    else:
                        st.warning("⚠️ Format necunoscut - chei disponibile:")
                        st.code(", ".join(data.keys()))
                
                if products:
                    # Afișează primele 3 produse
                    st.write("**📦 Primele 3 produse:**")
                    for i, prod in enumerate(products[:3], 1):
                        with st.expander(f"Produs {i}: {prod.get('productName', 'N/A')}"):
                            st.json(prod)
                    
                    # Analizează structura unui produs
                    sample = products[0]
                    st.write("**🔍 Structură produs (primul produs):**")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**Chei disponibile:**")
                        for key in sample.keys():
                            st.code(f"• {key}: {type(sample[key]).__name__}")
                    with col2:
                        st.write("**Valorile cheilor importante:**")
                        st.code(f"""productCode: {sample.get('productCode', 'N/A')}
productName: {sample.get('productName', 'N/A')}
quantity: {sample.get('quantity', 'N/A')}
measuringUnit: {sample.get('measuringUnit', 'N/A')}""")
                    
                    return products
                else:
                    st.warning("⚠️ Nu s-au găsit produse în răspuns")
                    return None
                    
            except json.JSONDecodeError:
                st.error("❌ Răspunsul nu este JSON valid")
                st.code(response.text[:500])
                return None
                
        elif response.status_code == 401:
            st.error("🔒 **EROARE 401**: Autentificare eșuată")
            st.warning("Verifică:")
            st.code("1. Email-ul este corect\n2. Token-ul API este valid\n3. Token-ul nu a expirat")
            st.code(response.text)
            return None
            
        elif response.status_code == 400:
            st.error("❌ **EROARE 400**: Request invalid")
            st.warning("Posibile cauze:")
            st.code("1. CIF-ul este greșit\n2. Numele gestiunii nu există\n3. Formatul datei este invalid")
            st.code(response.text)
            return None
            
        elif response.status_code == 404:
            st.error("❌ **EROARE 404**: Endpoint-ul nu există")
            st.warning(f"Verifică dacă URL-ul este corect: {url}")
            return None
            
        else:
            st.error(f"❌ **EROARE {response.status_code}**")
            st.code(response.text)
            return None
            
    except requests.exceptions.Timeout:
        st.error("⏱️ **TIMEOUT**: SmartBill nu răspunde în 30 secunde")
        return None
    except requests.exceptions.ConnectionError:
        st.error("🔌 **CONNECTION ERROR**: Nu se poate conecta la SmartBill")
        return None
    except Exception as e:
        st.error(f"❌ **Excepție neașteptată**: {type(e).__name__}")
        st.exception(e)
        return None

def test_smartbill_single_product(email, token, cif, product_code):
    """Test pentru un singur produs specific"""
    st.subheader(f"🧪 Test Produs Individual: `{product_code}`")
    
    try:
        url = "https://ws.smartbill.ro/SBORO/api/stocks"
        
        headers = {
            "Content-Type": "application/xml",
            "Accept": "application/json"
        }
        
        auth = HTTPBasicAuth(email, token)
        
        params = {
            "cif": cif,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "warehouseName": WAREHOUSE_NAME,
            "productCode": product_code
        }
        
        st.code(f"""Request:
GET {url}
CIF: {cif}
Warehouse: {WAREHOUSE_NAME}
Product Code: {product_code}
""", language="text")
        
        response = requests.get(
            url,
            auth=auth,
            headers=headers,
            params=params,
            timeout=30
        )
        
        st.write(f"**Status**: `{response.status_code}`")
        
        if response.status_code == 200:
            data = response.json()
            st.success(f"✅ Produs găsit în gestiunea '{WAREHOUSE_NAME}'!")
            
            with st.expander("📄 Detalii produs"):
                st.json(data)
            
            # Extrage și afișează informații key
            if isinstance(data, list) and len(data) > 0:
                prod = data[0]
            elif isinstance(data, dict):
                prod = data
            else:
                prod = None
            
            if prod:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Cod", prod.get('productCode', 'N/A'))
                with col2:
                    st.metric("Stoc", prod.get('quantity', 0))
                with col3:
                    st.metric("UM", prod.get('measuringUnit', 'buc'))
                
                st.info(f"**Denumire**: {prod.get('productName', 'N/A')}")
            
            return data
        elif response.status_code == 404:
            st.warning(f"⚠️ Produsul `{product_code}` nu a fost găsit în gestiune")
            return None
        else:
            st.error(f"❌ Eroare {response.status_code}")
            st.code(response.text)
            return None
            
    except Exception as e:
        st.error(f"Eroare: {str(e)}")
        return None

def test_woocommerce_connection(url, consumer_key, consumer_secret):
    """Test conexiune WooCommerce cu detalii"""
    st.subheader("🧪 Test Conexiune WooCommerce")
    
    try:
        endpoint = f"{url}/wp-json/wc/v3/products"
        
        params = {
            "per_page": 5,
            "page": 1
        }
        
        st.code(f"GET {endpoint}\nParams: per_page=5, page=1", language="text")
        
        response = requests.get(
            endpoint,
            auth=(consumer_key, consumer_secret),
            params=params,
            timeout=30
        )
        
        st.write(f"**Status Code**: `{response.status_code}`")
        
        if response.status_code == 200:
            products = response.json()
            total = response.headers.get('X-WP-Total', 'N/A')
            total_pages = response.headers.get('X-WP-TotalPages', 'N/A')
            
            st.success(f"✅ Conexiune reușită!")
            st.info(f"**Total produse în magazin**: {total} ({total_pages} pagini)")
            
            st.write("**📦 Primele 5 produse:**")
            
            for p in products:
                sku = p.get('sku', '❌ FĂRĂ SKU')
                name = p.get('name', 'N/A')
                stock = p.get('stock_quantity', 'N/A')
                status = p.get('stock_status', 'N/A')
                manage = p.get('manage_stock', False)
                
                with st.expander(f"{name}"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("SKU", sku)
                    with col2:
                        st.metric("Stoc", stock if stock is not None else "N/A")
                    with col3:
                        st.metric("Status", status)
                    st.write(f"**Gestionează stoc**: {'✅ Da' if manage else '❌ Nu'}")
            
            # Verifică produse fără SKU
            products_without_sku = [p for p in products if not p.get('sku')]
            if products_without_sku:
                st.warning(f"⚠️ {len(products_without_sku)} produse din 5 nu au SKU setat!")
            
            return products
            
        elif response.status_code == 401:
            st.error("🔒 **EROARE 401**: Consumer Key sau Secret invalid")
            st.code(response.text)
            return None
        elif response.status_code == 404:
            st.error("❌ **EROARE 404**: Endpoint-ul WooCommerce nu există")
            st.warning("Verifică dacă WooCommerce este instalat și activ")
            return None
        else:
            st.error(f"❌ Eroare {response.status_code}")
            st.code(response.text)
            return None
            
    except Exception as e:
        st.error(f"Eroare: {str(e)}")
        return None

def test_sku_comparison(email, token, cif, url, consumer_key, consumer_secret):
    """Test de comparare SKU-uri între SmartBill și WooCommerce"""
    st.subheader("🧪 Test Comparare SKU-uri")
    
    with st.spinner("Preluare date SmartBill..."):
        sb_data = get_smartbill_stocks(email, token, cif, WAREHOUSE_NAME, show_progress=False)
    
    with st.spinner("Preluare primele 20 produse WooCommerce..."):
        endpoint = f"{url}/wp-json/wc/v3/products"
        response = requests.get(
            endpoint,
            auth=(consumer_key, consumer_secret),
            params={"per_page": 20, "page": 1},
            timeout=30
        )
        woo_data = response.json() if response.status_code == 200 else []
    
    if sb_data and woo_data:
        sb_dict = process_smartbill_data(sb_data)
        woo_dict = process_woocommerce_data(woo_data)
        
        st.info(f"**SmartBill**: {len(sb_dict)} produse | **WooCommerce**: {len(woo_dict)} produse (primele 20)")
        
        # Găsește produse comune
        common_skus = set(sb_dict.keys()) & set(woo_dict.keys())
        
        st.success(f"✅ Găsite {len(common_skus)} SKU-uri comune din 20 testate")
        
        if common_skus:
            st.write("**Exemple de SKU-uri comune:**")
            for sku in list(common_skus)[:5]:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.code(f"SKU: {sku}")
                with col2:
                    st.metric("SmartBill", sb_dict[sku]['stock'])
                with col3:
                    st.metric("WooCommerce", woo_dict[sku]['stock'])
        
        # Verifică SKU-uri care nu se potrivesc
        sb_only = set(list(sb_dict.keys())[:20]) - set(woo_dict.keys())
        woo_only = set(woo_dict.keys()) - set(list(sb_dict.keys())[:20])
        
        if sb_only:
            st.warning(f"⚠️ {len(sb_only)} SKU-uri din SmartBill nu sunt în WooCommerce (din primele 20)")
            with st.expander("Vezi SKU-uri lipsă din WooCommerce"):
                for sku in list(sb_only)[:10]:
                    st.code(f"• {sku} - {sb_dict[sku]['name']}")
        
        if woo_only:
            st.warning(f"⚠️ {len(woo_only)} SKU-uri din WooCommerce nu sunt în SmartBill")
            with st.expander("Vezi SKU-uri lipsă din SmartBill"):
                for sku in list(woo_only)[:10]:
                    st.code(f"• {sku} - {woo_dict[sku]['name']}")
    else:
        st.error("Nu s-au putut prelua datele pentru comparație")

# ==================== FUNCȚII API PRINCIPALE ====================

def get_smartbill_stocks(email, token, cif, warehouse_name, show_progress=True):
    """Obține stocurile din SmartBill pentru gestiunea specifică"""
    try:
        url = "https://ws.smartbill.ro/SBORO/api/stocks"
        
        headers = {
            "Content-Type": "application/xml",
            "Accept": "application/json"
        }
        
        auth = HTTPBasicAuth(email, token)
        
        params = {
            "cif": cif,
            "date": datetime.now().strftime("%Y-%m-%d"),
            "warehouseName": warehouse_name
        }
        
        response = requests.get(
            url,
            auth=auth,
            headers=headers,
            params=params,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            if show_progress:
                st.error("🔒 Autentificare eșuată SmartBill")
            return None
        else:
            if show_progress:
                st.error(f"Eroare SmartBill API: {response.status_code}")
                with st.expander("Detalii eroare"):
                    st.code(response.text)
            return None
            
    except Exception as e:
        if show_progress:
            st.error(f"Eroare SmartBill: {str(e)}")
        return None

def get_woocommerce_products(url, consumer_key, consumer_secret):
    """Obține toate produsele din WooCommerce"""
    try:
        all_products = []
        page = 1
        per_page = 100
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Primul request pentru total
        endpoint = f"{url}/wp-json/wc/v3/products"
        response = requests.get(
            endpoint,
            auth=(consumer_key, consumer_secret),
            params={"per_page": 1, "page": 1},
            timeout=30
        )
        
        if response.status_code != 200:
            st.error(f"Eroare WooCommerce: {response.status_code}")
            progress_bar.empty()
            status_text.empty()
            return []
        
        total_products = int(response.headers.get('X-WP-Total', 0))
        total_pages = int(response.headers.get('X-WP-TotalPages', 1))
        
        status_text.text(f"Se preiau {total_products} produse din WooCommerce...")
        
        while page <= total_pages:
            params = {
                "per_page": per_page,
                "page": page,
                "status": "publish"
            }
            
            response = requests.get(
                endpoint,
                auth=(consumer_key, consumer_secret),
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                products = response.json()
                if not products:
                    break
                all_products.extend(products)
                
                progress = min(page / total_pages, 1.0)
                progress_bar.progress(progress)
                status_text.text(f"Preluate {len(all_products)} / {total_products} produse...")
                
                page += 1
                time.sleep(0.1)  # Rate limiting
            else:
                st.error(f"Eroare pagina {page}: {response.status_code}")
                break
        
        progress_bar.empty()
        status_text.empty()
        
        return all_products
        
    except Exception as e:
        st.error(f"Eroare WooCommerce: {str(e)}")
        return []

def process_smartbill_data(data):
    """Procesează datele SmartBill conform documentației"""
    sb_dict = {}
    
    if not data:
        return sb_dict
    
    # Extrage lista de produse
    products = []
    if isinstance(data, list):
        products = data
    elif isinstance(data, dict):
        products = data.get('products', [])
    
    # Procesează fiecare produs
    for item in products:
        code = item.get('productCode', '').strip()
        name = item.get('productName', '').strip()
        quantity = item.get('quantity', '0')
        unit = item.get('measuringUnit', 'buc')
        
        # Warehouse info
        warehouse = item.get('warehouse', {})
        if isinstance(warehouse, dict):
            warehouse_name = warehouse.get('warehouseName', '')
        else:
            warehouse_name = ''
        
        # Convertește quantity la float
        try:
            quantity = float(quantity) if quantity else 0
        except (ValueError, TypeError):
            quantity = 0
        
        if code:  # Adaugă doar produse cu cod valid
            sb_dict[code] = {
                'name': name,
                'stock': quantity,
                'unit': unit,
                'warehouse': warehouse_name
            }
    
    return sb_dict

def process_woocommerce_data(products):
    """Procesează datele WooCommerce"""
    woo_dict = {}
    
    for product in products:
        sku = product.get('sku', '').strip()
        
        if not sku:  # Skip produse fără SKU
            continue
        
        stock_qty = product.get('stock_quantity')
        if stock_qty is None:
            stock_qty = 0
        else:
            try:
                stock_qty = float(stock_qty)
            except (ValueError, TypeError):
                stock_qty = 0
        
        woo_dict[sku] = {
            'name': product.get('name', ''),
            'stock': stock_qty,
            'status': product.get('stock_status', 'outofstock'),
            'manage_stock': product.get('manage_stock', False),
            'id': product.get('id', 0)
        }
    
    return woo_dict

def generate_discrepancy_report(sb_dict, woo_dict):
    """Generează raport detaliat cu discrepanțe"""
    discrepancies = []
    
    # 1. Produse în SmartBill cu stoc > 0 dar lipsesc din WooCommerce
    for code, sb_info in sb_dict.items():
        if code not in woo_dict and sb_info['stock'] > 0:
            discrepancies.append({
                'Cod': code,
                'Denumire': sb_info['name'],
                'Stoc SmartBill': sb_info['stock'],
                'Stoc WooCommerce': 'N/A',
                'Diferență': sb_info['stock'],
                'Tip': '❌ Lipsește din WooCommerce',
                'Status': 'CRITIC',
                'Prioritate': 1
            })
    
    # 2. Produse cu stoc în SmartBill dar 0 în WooCommerce
    for code, sb_info in sb_dict.items():
        if code in woo_dict and sb_info['stock'] > 0 and woo_dict[code]['stock'] == 0:
            discrepancies.append({
                'Cod': code,
                'Denumire': sb_info['name'],
                'Stoc SmartBill': sb_info['stock'],
                'Stoc WooCommerce': 0,
                'Diferență': sb_info['stock'],
                'Tip': '⚠️ Stoc 0 în WooCommerce',
                'Status': 'ATENTIE',
                'Prioritate': 2
            })
    
    # 3. Diferențe de cantitate (toleranță 0.01 pentru erori de rotunjire)
    for code in set(sb_dict.keys()) & set(woo_dict.keys()):
        sb_stock = sb_dict[code]['stock']
        woo_stock = woo_dict[code]['stock']
        diff = sb_stock - woo_stock
        
        if abs(diff) > 0.01:
            if sb_stock > 0 or woo_stock > 0:  # Ignoră ambele 0
                discrepancies.append({
                    'Cod': code,
                    'Denumire': sb_dict[code]['name'],
                    'Stoc SmartBill': sb_stock,
                    'Stoc WooCommerce': woo_stock,
                    'Diferență': round(diff, 2),
                    'Tip': '🔄 Diferență cantitate',
                    'Status': 'SINCRONIZARE',
                    'Prioritate': 3
                })
    
    # 4. Produse în WooCommerce cu stoc > 0 dar nu există în SmartBill
    for code, woo_info in woo_dict.items():
        if code not in sb_dict and woo_info['stock'] > 0:
            discrepancies.append({
                'Cod': code,
                'Denumire': woo_info['name'],
                'Stoc SmartBill': 0,
                'Stoc WooCommerce': woo_info['stock'],
                'Diferență': -woo_info['stock'],
                'Tip': '🚫 În WooCommerce dar nu în SmartBill',
                'Status': 'CRITIC',
                'Prioritate': 1
            })
    
    df = pd.DataFrame(discrepancies)
    
    if len(df) > 0:
        df = df.sort_values(['Prioritate', 'Stoc SmartBill'], ascending=[True, False])
        df = df.drop('Prioritate', axis=1)
    
    return df

# ==================== UI PRINCIPAL ====================

def main():
    # Tabs
    tab1, tab2 = st.tabs(["🧪 Mod Test", "🚀 Verificare Completă"])
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configurări")
        
        st.subheader("🔵 SmartBill")
        try:
            sb_email = st.secrets["smartbill"]["email"]
            sb_token = st.secrets["smartbill"]["token"]
            sb_cif = st.secrets["smartbill"]["cif"]
            st.success("✅ Din secrets")
        except:
            sb_email = st.text_input("Email", value="mobilepointgsm@gmail.com")
            sb_token = st.text_input("Token", value="6a318b8324acba9d4cc360bb9cf48e45", type="password")
            sb_cif = st.text_input("CIF", value="RO36898183")
        
        st.info(f"**Gestiune**: {WAREHOUSE_NAME}\n**Tip**: {WAREHOUSE_TYPE}")
        
        st.markdown("---")
        
        st.subheader("🟢 WooCommerce")
        try:
            woo_url = st.secrets["woocommerce"]["url"]
            woo_key = st.secrets["woocommerce"]["consumer_key"]
            woo_secret = st.secrets["woocommerce"]["consumer_secret"]
            st.success("✅ Din secrets")
        except:
            woo_url = st.text_input("URL", value="https://servicepack.ro")
            woo_key = st.text_input("Consumer Key", type="password")
            woo_secret = st.text_input("Consumer Secret", type="password")
    
    # TAB 1: MOD TEST
    with tab1:
        st.header("🧪 Suite de Testare API")
        st.info("Rulează testele pentru a verifica că toate API-urile funcționează corect înainte de verificarea completă.")
        
        test_col1, test_col2 = st.columns(2)
        
        with test_col1:
            st.subheader("SmartBill Tests")
            
            if st.button("🔵 1. Test Conexiune Bază", use_container_width=True, type="primary"):
                if all([sb_email, sb_token, sb_cif]):
                    test_smartbill_connection(sb_email, sb_token, sb_cif)
                else:
                    st.error("Completează credențialele SmartBill!")
            
            test_product_code = st.text_input("Cod produs pentru test", placeholder="Ex: IP14-PM-256-BLK", help="Introdu un SKU care există în SmartBill")
            if st.button("🔵 2. Test Produs Specific", use_container_width=True):
                if test_product_code and all([sb_email, sb_token, sb_cif]):
                    test_smartbill_single_product(sb_email, sb_token, sb_cif, test_product_code)
                else:
                    st.error("Completează codul produsului și credențialele!")
        
        with test_col2:
            st.subheader("WooCommerce Tests")
            
            if st.button("🟢 3. Test Conexiune WooCommerce", use_container_width=True, type="primary"):
                if all([woo_url, woo_key, woo_secret]):
                    test_woocommerce_connection(woo_url, woo_key, woo_secret)
                else:
                    st.error("Completează credențialele WooCommerce!")
        
        st.markdown("---")
        
        if st.button("🔄 4. Test Comparare SKU-uri (20 produse)", use_container_width=True):
            if all([sb_email, sb_token, sb_cif, woo_url, woo_key, woo_secret]):
                test_sku_comparison(sb_email, sb_token, sb_cif, woo_url, woo_key, woo_secret)
            else:
                st.error("Completează toate credențialele!")
    
    # TAB 2: VERIFICARE COMPLETĂ
    with tab2:
        st.header("🚀 Verificare Completă Stocuri")
        st.info(f"Gestiune: **{WAREHOUSE_NAME}** (tip: {WAREHOUSE_TYPE})")
        
        if st.button("▶️ Pornește Verificarea Completă", type="primary", use_container_width=True):
            if not all([sb_email, sb_token, sb_cif, woo_url, woo_key, woo_secret]):
                st.error("⚠️ Completează toate credențialele în sidebar!")
                return
            
            start_time = time.time()
            
            col1, col2 = st.columns(2)
            
            with col1:
                with st.spinner("📥 Preluare SmartBill..."):
                    sb_data = get_smartbill_stocks(sb_email, sb_token, sb_cif, WAREHOUSE_NAME)
            
            with col2:
                with st.spinner("📥 Preluare WooCommerce..."):
                    woo_data = get_woocommerce_products(woo_url, woo_key, woo_secret)
            
            if sb_data is not None and woo_data:
                sb_dict = process_smartbill_data(sb_data)
                woo_dict = process_woocommerce_data(woo_data)
                
                elapsed = time.time() - start_time
                st.success(f"✅ Date preluate în {elapsed:.1f}s: **{len(sb_dict)}** produse SmartBill | **{len(woo_dict)}** produse WooCommerce")
                
                # Generare raport
                df_report = generate_discrepancy_report(sb_dict, woo_dict)
                
                if len(df_report) > 0:
                    st.markdown("---")
                    st.header("📊 Raport Discrepanțe")
                    
                    # Metrici
                    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                    with metric_col1:
                        critic_count = len(df_report[df_report['Status'] == 'CRITIC'])
                        st.metric("🔴 Critice", critic_count)
                    with metric_col2:
                        atentie_count = len(df_report[df_report['Status'] == 'ATENTIE'])
                        st.metric("🟡 Atenție", atentie_count)
                    with metric_col3:
                        sync_count = len(df_report[df_report['Status'] == 'SINCRONIZARE'])
                        st.metric("🔵 Sincronizare", sync_count)
                    with metric_col4:
                        st.metric("📝 Total Discrepanțe", len(df_report))
                    
                    st.markdown("---")
                    
                    # Filtre
                    filter_col1, filter_col2 = st.columns([1, 2])
                    with filter_col1:
                        status_filter = st.multiselect(
                            "Filtrează după status",
                            options=df_report['Status'].unique(),
                            default=df_report['Status'].unique()
                        )
                    with filter_col2:
                        search = st.text_input("🔎 Caută după cod sau denumire")
                    
                    # Aplicare filtre
                    df_filtered = df_report[df_report['Status'].isin(status_filter)]
                    
                    if search:
                        mask = (
                            df_filtered['Cod'].astype(str).str.contains(search, case=False, na=False) |
                            df_filtered['Denumire'].astype(str).str.contains(search, case=False, na=False)
                        )
                        df_filtered = df_filtered[mask]
                    
                    # Tabel
                    st.dataframe(
                        df_filtered,
                        use_container_width=True,
                        height=450,
                        hide_index=True
                    )
                    
                    st.caption(f"Afișate {len(df_filtered)} din {len(df_report)} discrepanțe")
                    
                    # Export
                    export_col1, export_col2, export_col3 = st.columns([2, 1, 1])
                    
                    with export_col2:
                        csv = df_filtered.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            "📥 Descarcă CSV",
                            data=csv,
                            file_name=f"raport_stocuri_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                    
                    with export_col3:
                        excel_buffer = create_excel_report(df_filtered)
                        st.download_button(
                            "📊 Descarcă Excel",
                            data=excel_buffer,
                            file_name=f"raport_stocuri_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                    
                else:
                    st.success("🎉 Excelent! Nu s-au găsit discrepanțe între SmartBill și WooCommerce!")
                    st.balloons()
                    
                    # Afișează statistici generale
                    st.markdown("---")
                    st.subheader("📈 Statistici Generale")
                    
                    stat_col1, stat_col2, stat_col3 = st.columns(3)
                    with stat_col1:
                        total_stock_sb = sum(v['stock'] for v in sb_dict.values())
                        st.metric("Total Stoc SmartBill", f"{total_stock_sb:.0f} buc")
                    with stat_col2:
                        total_stock_woo = sum(v['stock'] for v in woo_dict.values())
                        st.metric("Total Stoc WooCommerce", f"{total_stock_woo:.0f} buc")
                    with stat_col3:
                        match_rate = len(set(sb_dict.keys()) & set(woo_dict.keys())) / max(len(sb_dict), len(woo_dict)) * 100
                        st.metric("Rata de potrivire", f"{match_rate:.1f}%")
            
            else:
                st.error("❌ Nu s-au putut prelua datele. Verifică credențialele și încearcă din nou.")

def create_excel_report(df):
    """Creează un fișier Excel cu formatare"""
    import io
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Discrepante', index=False)
    
    return output.getvalue()

if __name__ == "__main__":
    main()
