import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from datetime import datetime
import time
import json
import io

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
WAREHOUSE_TYPE = "en gros"

# ==================== FUNCȚII DE TEST ====================

def test_smartbill_connection(email, token, cif):
    """Test complet pentru conexiunea SmartBill cu debug detaliat"""
    st.subheader("🧪 Test Conexiune SmartBill")
    
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
                
                with st.expander("📄 Structură JSON completă (primele 1000 caractere)", expanded=False):
                    json_str = json.dumps(data, indent=2, ensure_ascii=False)
                    st.code(json_str[:1000], language="json")
                    st.caption(f"Total lungime: {len(json_str)} caractere")
                
                st.write("### 🔍 Analiză Structură")
                st.write("**Tip root object**:", type(data).__name__)
                
                if isinstance(data, dict):
                    st.write("**Chei root**:", list(data.keys()))
                    
                    if "list" in data:
                        list_data = data["list"]
                        st.write(f"**data['list']** lungime:", len(list_data) if isinstance(list_data, list) else "N/A")
                        
                        if isinstance(list_data, list) and len(list_data) > 0:
                            first_item = list_data[0]
                            if isinstance(first_item, dict):
                                st.write("**data['list'][0]** chei:", list(first_item.keys()))
                                
                                if "warehouse" in first_item:
                                    st.write("**Warehouse info**:")
                                    st.json(first_item["warehouse"])
                                
                                if "products" in first_item:
                                    products = first_item["products"]
                                    st.write(f"**Total produse găsite**: {len(products)}")
                                    
                                    if len(products) > 0:
                                        with st.expander("📦 Primul produs"):
                                            st.json(products[0])
                                        
                                        st.write("### 🧪 Test Procesare")
                                        sb_dict = process_smartbill_data(data, debug=True)
                                        
                                        if sb_dict:
                                            st.success(f"✅ Procesare reușită! {len(sb_dict)} produse")
                                            
                                            st.write("**Primele 5 produse procesate**:")
                                            for i, (code, info) in enumerate(list(sb_dict.items())[:5], 1):
                                                col1, col2, col3, col4 = st.columns([2, 4, 1, 1])
                                                with col1:
                                                    st.code(code)
                                                with col2:
                                                    st.write(info['name'][:50] + "..." if len(info['name']) > 50 else info['name'])
                                                with col3:
                                                    st.metric("Stoc", info['stock'])
                                                with col4:
                                                    st.write(info['unit'])
                                        
                                        return products
                
                return data
                    
            except json.JSONDecodeError:
                st.error("❌ Răspunsul nu este JSON valid")
                st.code(response.text[:500])
                return None
                
        elif response.status_code == 401:
            st.error("🔒 **EROARE 401**: Autentificare eșuată")
            st.code(response.text)
            return None
        else:
            st.error(f"❌ **EROARE {response.status_code}**")
            st.code(response.text)
            return None
            
    except Exception as e:
        st.error(f"❌ **Excepție**: {str(e)}")
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
            st.success(f"✅ Răspuns primit!")
            
            with st.expander("📄 Răspuns complet"):
                st.json(data)
            
            sb_dict = process_smartbill_data(data, debug=True)
            
            if product_code in sb_dict:
                prod = sb_dict[product_code]
                st.success(f"✅ Produs găsit!")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Cod", product_code)
                with col2:
                    st.metric("Stoc", prod['stock'])
                with col3:
                    st.metric("UM", prod['unit'])
                
                st.info(f"**Denumire**: {prod['name']}")
            else:
                st.warning(f"⚠️ Produsul nu a fost găsit în răspuns")
            
            return data
        else:
            st.error(f"❌ Eroare {response.status_code}")
            st.code(response.text)
            return None
            
    except Exception as e:
        st.error(f"Eroare: {str(e)}")
        return None

def test_woocommerce_connection(url, consumer_key, consumer_secret):
    """Test conexiune WooCommerce"""
    st.subheader("🧪 Test Conexiune WooCommerce")
    
    try:
        endpoint = f"{url}/wp-json/wc/v3/products"
        
        response = requests.get(
            endpoint,
            auth=(consumer_key, consumer_secret),
            params={"per_page": 5, "page": 1},
            timeout=30
        )
        
        st.write(f"**Status Code**: `{response.status_code}`")
        
        if response.status_code == 200:
            products = response.json()
            total = response.headers.get('X-WP-Total', 'N/A')
            
            st.success(f"✅ Conexiune reușită! Total produse: {total}")
            
            st.write("**📦 Primele 5 produse:**")
            for p in products:
                prod_type = p.get('type', 'N/A')
                sku = p.get('sku', '❌ FĂRĂ SKU')
                name = p.get('name', 'N/A')
                stock = p.get('stock_quantity', 'N/A')
                
                with st.expander(f"{name[:60]}... [{prod_type}]"):
                    st.write(f"**Tip**: {prod_type}")
                    st.write(f"**SKU**: {sku}")
                    st.write(f"**Stoc**: {stock}")
                    if prod_type == 'variable':
                        st.info("⚠️ Produs variabil - variațiile vor fi preluate separat")
            
            return products
        else:
            st.error(f"❌ Eroare {response.status_code}")
            st.code(response.text)
            return None
            
    except Exception as e:
        st.error(f"Eroare: {str(e)}")
        return None

def test_sku_comparison(email, token, cif, url, consumer_key, consumer_secret):
    """Test comparare SKU-uri"""
    st.subheader("🧪 Test Comparare SKU-uri")
    
    with st.spinner("Preluare SmartBill..."):
        sb_data = get_smartbill_stocks(email, token, cif, WAREHOUSE_NAME, show_progress=False)
    
    with st.spinner("Preluare WooCommerce (primele 50 produse + variații)..."):
        woo_data = get_woocommerce_products(url, consumer_key, consumer_secret, max_products=50)
    
    if sb_data and woo_data:
        sb_dict = process_smartbill_data(sb_data, debug=False)
        woo_dict = process_woocommerce_data(woo_data)
        
        st.info(f"**SmartBill**: {len(sb_dict)} | **WooCommerce**: {len(woo_dict)}")
        
        common = set(sb_dict.keys()) & set(woo_dict.keys())
        
        if common:
            st.success(f"✅ {len(common)} SKU-uri comune")
            
            with st.expander("Vezi primele 5 SKU-uri comune"):
                for sku in list(common)[:5]:
                    st.write(f"**{sku}**: SB={sb_dict[sku]['stock']}, WOO={woo_dict[sku]['stock']}")
        else:
            st.warning("⚠️ Nu s-au găsit SKU-uri comune!")
    else:
        st.error("Nu s-au putut prelua datele")

# ==================== FUNCȚII API PRINCIPALE ====================

def get_smartbill_stocks(email, token, cif, warehouse_name, show_progress=True):
    """Obține stocurile din SmartBill"""
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
        
        if show_progress:
            st.info(f"🔍 SmartBill: '{warehouse_name}'")
        
        response = requests.get(url, auth=auth, headers=headers, params=params, timeout=30)
        
        if show_progress:
            st.write(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            if show_progress:
                if isinstance(data, dict) and "list" in data:
                    total = sum(len(w.get("products", [])) for w in data["list"] if isinstance(w, dict))
                    st.success(f"✅ {total} produse SmartBill")
            
            return data
        else:
            if show_progress:
                st.error(f"Eroare SmartBill: {response.status_code}")
            return None
            
    except Exception as e:
        if show_progress:
            st.error(f"Eroare SmartBill: {str(e)}")
        return None

def get_woocommerce_products(url, consumer_key, consumer_secret, max_products=None):
    """
    Preluare produse WooCommerce:
    - Produse simple: SE PREIAU
    - Produse variabile: NU SE PREIAU (doar parent)
    - Variații: SE PREIAU
    """
    try:
        all_items = []
        page = 1
        per_page = 100
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        endpoint = f"{url}/wp-json/wc/v3/products"
        
        # Get total
        response = requests.get(endpoint, auth=(consumer_key, consumer_secret), params={"per_page": 1}, timeout=30)
        
        if response.status_code != 200:
            st.error(f"Eroare WooCommerce: {response.status_code}")
            return []
        
        total_products = int(response.headers.get('X-WP-Total', 0))
        total_pages = int(response.headers.get('X-WP-TotalPages', 1))
        
        if max_products:
            total_pages = min(total_pages, (max_products // per_page) + 1)
        
        status_text.text(f"Preluare produse WooCommerce...")
        
        # STEP 1: Preluare toate produsele (simple + variable)
        products_data = []
        while page <= total_pages:
            response = requests.get(
                endpoint,
                auth=(consumer_key, consumer_secret),
                params={"per_page": per_page, "page": page, "status": "publish"},
                timeout=30
            )
            
            if response.status_code == 200:
                products = response.json()
                if not products:
                    break
                products_data.extend(products)
                
                progress_bar.progress(min(page / (total_pages * 2), 0.5))
                status_text.text(f"Produse: {len(products_data)}...")
                
                page += 1
                time.sleep(0.1)
            else:
                break
        
        # Separă produsele simple de cele variabile
        simple_products = [p for p in products_data if p.get('type') in ['simple', 'external', 'grouped']]
        variable_products = [p for p in products_data if p.get('type') == 'variable']
        
        # Adaugă produsele simple
        all_items.extend(simple_products)
        
        status_text.text(f"Produse simple: {len(simple_products)}, Variabile: {len(variable_products)}")
        
        # STEP 2: Pentru fiecare produs variabil, preluare variații
        if variable_products:
            status_text.text(f"Preluare variații pentru {len(variable_products)} produse...")
            
            total_variations = 0
            for idx, var_product in enumerate(variable_products):
                product_id = var_product['id']
                var_page = 1
                
                while True:
                    variations_endpoint = f"{url}/wp-json/wc/v3/products/{product_id}/variations"
                    var_response = requests.get(
                        variations_endpoint,
                        auth=(consumer_key, consumer_secret),
                        params={"per_page": 100, "page": var_page},
                        timeout=30
                    )
                    
                    if var_response.status_code == 200:
                        variations = var_response.json()
                        if not variations:
                            break
                        
                        all_items.extend(variations)
                        total_variations += len(variations)
                        var_page += 1
                        time.sleep(0.05)
                    else:
                        break
                
                # Update progress
                progress = 0.5 + (0.5 * (idx + 1) / len(variable_products))
                progress_bar.progress(min(progress, 1.0))
                status_text.text(f"Variații prelucrate: {total_variations}...")
        
        progress_bar.empty()
        status_text.empty()
        
        return all_items
        
    except Exception as e:
        st.error(f"Eroare WooCommerce: {str(e)}")
        return []

def process_smartbill_data(data, debug=False):
    """Procesează datele SmartBill"""
    sb_dict = {}
    
    if not data:
        return sb_dict
    
    products = []
    
    if isinstance(data, dict) and "list" in data:
        for warehouse_item in data["list"]:
            if isinstance(warehouse_item, dict) and "products" in warehouse_item:
                products.extend(warehouse_item["products"])
    elif isinstance(data, dict) and "products" in data:
        products = data["products"]
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                if "list" in item:
                    for w in item["list"]:
                        if "products" in w:
                            products.extend(w["products"])
                elif "products" in item:
                    products.extend(item["products"])
                elif "productCode" in item:
                    products.append(item)
    
    if debug:
        st.write(f"**Produse extrase**: {len(products)}")
    
    for product in products:
        if not isinstance(product, dict):
            continue
            
        code = product.get('productCode', '').strip()
        name = product.get('productName', '').strip()
        quantity = product.get('quantity', 0)
        unit = product.get('measuringUnit', 'buc')
        
        try:
            quantity = float(quantity) if quantity else 0
        except:
            quantity = 0
        
        if code:
            sb_dict[code] = {
                'name': name,
                'stock': quantity,
                'unit': unit
            }
    
    if debug:
        st.write(f"**Produse procesate**: {len(sb_dict)}")
    
    return sb_dict

def process_woocommerce_data(products):
    """
    Procesează produse WooCommerce
    Include doar produse cu SKU (simple și variații)
    """
    woo_dict = {}
    
    for product in products:
        sku = product.get('sku', '').strip()
        
        if not sku:
            continue
        
        stock_qty = product.get('stock_quantity')
        try:
            stock_qty = float(stock_qty) if stock_qty is not None else 0
        except:
            stock_qty = 0
        
        woo_dict[sku] = {
            'name': product.get('name', ''),
            'stock': stock_qty,
            'status': product.get('stock_status', 'outofstock'),
            'manage_stock': product.get('manage_stock', False),
            'id': product.get('id', 0),
            'type': product.get('type', 'unknown')
        }
    
    return woo_dict

def generate_discrepancy_report(sb_dict, woo_dict):
    """Generează raport discrepanțe"""
    discrepancies = []
    
    # 1. În SmartBill cu stoc > 0 dar lipsă din WooCommerce
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
    
    # 2. Stoc în SmartBill dar 0 în WooCommerce
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
    
    # 3. Diferențe cantitate
    for code in set(sb_dict.keys()) & set(woo_dict.keys()):
        sb_stock = sb_dict[code]['stock']
        woo_stock = woo_dict[code]['stock']
        diff = sb_stock - woo_stock
        
        if abs(diff) > 0.01 and (sb_stock > 0 or woo_stock > 0):
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
    
    # 4. În WooCommerce cu stoc > 0 dar nu în SmartBill
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

def create_excel_report(df):
    """Creează Excel"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Discrepante', index=False)
    return output.getvalue()

# ==================== UI PRINCIPAL ====================

def main():
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
    
    # TAB 1: TESTE
    with tab1:
        st.header("🧪 Suite de Testare")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔵 1. Test SmartBill", use_container_width=True, type="primary"):
                if all([sb_email, sb_token, sb_cif]):
                    test_smartbill_connection(sb_email, sb_token, sb_cif)
                else:
                    st.error("Completează credențialele!")
            
            test_sku = st.text_input("SKU test", placeholder="GH82-30476B")
            if st.button("🔵 2. Test Produs", use_container_width=True):
                if test_sku and all([sb_email, sb_token, sb_cif]):
                    test_smartbill_single_product(sb_email, sb_token, sb_cif, test_sku)
                else:
                    st.error("Introdu SKU!")
        
        with col2:
            if st.button("🟢 3. Test WooCommerce", use_container_width=True, type="primary"):
                if all([woo_url, woo_key, woo_secret]):
                    test_woocommerce_connection(woo_url, woo_key, woo_secret)
                else:
                    st.error("Completează credențialele!")
        
        st.markdown("---")
        
        if st.button("🔄 4. Test Comparare SKU", use_container_width=True):
            if all([sb_email, sb_token, sb_cif, woo_url, woo_key, woo_secret]):
                test_sku_comparison(sb_email, sb_token, sb_cif, woo_url, woo_key, woo_secret)
            else:
                st.error("Completează toate credențialele!")
    
    # TAB 2: VERIFICARE
    with tab2:
        st.header("🚀 Verificare Completă")
        st.info(f"Gestiune: **{WAREHOUSE_NAME}** | Tip: {WAREHOUSE_TYPE}")
        
        debug_mode = st.checkbox("🐛 Mod Debug", value=False)
        
        if st.button("▶️ Pornește Verificarea", type="primary", use_container_width=True):
            if not all([sb_email, sb_token, sb_cif, woo_url, woo_key, woo_secret]):
                st.error("⚠️ Completează toate credențialele!")
                return
            
            start_time = time.time()
            st.markdown("---")
            
            # SmartBill
            st.subheader("📥 SmartBill")
            with st.spinner("Preluare..."):
                sb_data = get_smartbill_stocks(sb_email, sb_token, sb_cif, WAREHOUSE_NAME, show_progress=True)
            
            if not sb_data:
                st.error("❌ Eroare SmartBill")
                return
            
            if debug_mode:
                with st.expander("🐛 Debug SmartBill JSON"):
                    st.json(sb_data)
            
            sb_dict = process_smartbill_data(sb_data, debug=debug_mode)
            
            if not sb_dict:
                st.error("❌ Nu s-au procesat produse SmartBill")
                return
            
            st.success(f"✅ SmartBill: {len(sb_dict)} produse")
            st.markdown("---")
            
            # WooCommerce
            st.subheader("📥 WooCommerce")
            with st.spinner("Preluare produse + variații..."):
                woo_data = get_woocommerce_products(woo_url, woo_key, woo_secret)
            
            if not woo_data:
                st.error("❌ Eroare WooCommerce")
                return
            
            woo_dict = process_woocommerce_data(woo_data)
            
            if not woo_dict:
                st.error("❌ Nu s-au procesat produse WooCommerce")
                return
            
            st.success(f"✅ WooCommerce: {len(woo_dict)} produse (simple + variații)")
            
            elapsed = time.time() - start_time
            st.info(f"⏱️ Timp: {elapsed:.1f}s")
            st.markdown("---")
            
            # Debug overlap
            if debug_mode:
                st.write("### 🐛 Debug Overlap")
                common = set(sb_dict.keys()) & set(woo_dict.keys())
                st.write(f"SKU-uri comune: {len(common)}")
                st.write(f"Doar SmartBill: {len(set(sb_dict.keys()) - set(woo_dict.keys()))}")
                st.write(f"Doar WooCommerce: {len(set(woo_dict.keys()) - set(sb_dict.keys()))}")
                
                if common:
                    with st.expander("Vezi 10 SKU-uri comune"):
                        for sku in list(common)[:10]:
                            st.write(f"**{sku}**: SB={sb_dict[sku]['stock']}, WOO={woo_dict[sku]['stock']}")
            
            # Raport
            df_report = generate_discrepancy_report(sb_dict, woo_dict)
            
            if len(df_report) > 0:
                st.header("📊 Raport Discrepanțe")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("🔴 Critice", len(df_report[df_report['Status'] == 'CRITIC']))
                with col2:
                    st.metric("🟡 Atenție", len(df_report[df_report['Status'] == 'ATENTIE']))
                with col3:
                    st.metric("🔵 Sincronizare", len(df_report[df_report['Status'] == 'SINCRONIZARE']))
                with col4:
                    st.metric("📝 Total", len(df_report))
                
                st.markdown("---")
                
                # Filtre
                fc1, fc2 = st.columns([1, 2])
                with fc1:
                    status_filter = st.multiselect(
                        "Status",
                        options=df_report['Status'].unique(),
                        default=df_report['Status'].unique()
                    )
                with fc2:
                    search = st.text_input("🔎 Caută")
                
                df_filtered = df_report[df_report['Status'].isin(status_filter)]
                
                if search:
                    mask = (
                        df_filtered['Cod'].astype(str).str.contains(search, case=False, na=False) |
                        df_filtered['Denumire'].astype(str).str.contains(search, case=False, na=False)
                    )
                    df_filtered = df_filtered[mask]
                
                st.dataframe(df_filtered, use_container_width=True, height=450, hide_index=True)
                st.caption(f"Afișate {len(df_filtered)} din {len(df_report)}")
                
                # Export
                ec1, ec2, ec3 = st.columns([2, 1, 1])
                with ec2:
                    csv = df_filtered.to_csv(index=False).encode('utf-8-sig')
                    st.download_button(
                        "📥 CSV",
                        data=csv,
                        file_name=f"raport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                with ec3:
                    try:
                        excel = create_excel_report(df_filtered)
                        st.download_button(
                            "📊 Excel",
                            data=excel,
                            file_name=f"raport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                    except:
                        pass
            else:
                st.success("🎉 Nu există discrepanțe!")
                st.balloons()

if __name__ == "__main__":
    main()
