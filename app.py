"""
Aplicație Streamlit completă pentru:
1. Sincronizare WooCommerce → Supabase
2. Raportare discrepanțe SmartBill vs WooCommerce
"""

import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import time
import io

# ====================== CONFIGURARE ======================

st.set_page_config(
    page_title="Verificare Stoc SmartBill vs WooCommerce",
    page_icon="📦",
    layout="wide"
)

WAREHOUSE_NAME = "Eroilor 19 cv"
WAREHOUSE_TYPE = "en gros"

# ====================== SIDEBAR ======================

with st.sidebar:
    st.header("⚙️ Configurări")
    
    st.subheader("🔵 SmartBill")
    try:
        sb_email = st.secrets["smartbill"]["email"]
        sb_token = st.secrets["smartbill"]["token"]
        sb_cif = st.secrets["smartbill"]["cif"]
        st.success("✅ Credențiale SmartBill")
    except:
        sb_email = st.text_input("Email SmartBill", value="mobilepointgsm@gmail.com")
        sb_token = st.text_input("Token SmartBill", type="password")
        sb_cif = st.text_input("CIF", value="RO36898183")
    
    st.info(f"**Gestiune**: {WAREHOUSE_NAME}\n**Tip**: {WAREHOUSE_TYPE}")
    st.markdown("---")
    
    st.subheader("🟢 WooCommerce")
    try:
        woo_url = st.secrets["woocommerce"]["url"]
        woo_key = st.secrets["woocommerce"]["consumer_key"]
        woo_secret = st.secrets["woocommerce"]["consumer_secret"]
        st.success("✅ Credențiale WooCommerce")
    except:
        woo_url = st.text_input("URL WooCommerce", value="https://servicepack.ro")
        woo_key = st.text_input("Consumer Key", type="password")
        woo_secret = st.text_input("Consumer Secret", type="password")
    
    st.markdown("---")
    
    st.subheader("💾 Supabase")
    try:
        supabase_url = st.secrets["supabase"]["url"]
        supabase_key = st.secrets["supabase"]["key"]
        supabase: Client = create_client(supabase_url, supabase_key)
        st.success("✅ Conectat Supabase")
    except:
        supabase_url = st.text_input("Supabase URL")
        supabase_key = st.text_input("Supabase Key", type="password")
        if supabase_url and supabase_key:
            try:
                supabase = create_client(supabase_url, supabase_key)
                st.success("✅ Conectat")
            except:
                st.error("❌ Eroare conectare")
                supabase = None
        else:
            supabase = None

# ====================== FUNCȚII SYNC WOOCOMMERCE ======================

def sync_woocommerce_to_supabase(woo_url, woo_key, woo_secret, supabase_client):
    """
    Sincronizează toate produsele WooCommerce (simple + variații) în Supabase
    """
    
    sync_container = st.container()
    
    with sync_container:
        st.markdown("---")
        st.subheader("🔄 Sincronizare WooCommerce → Supabase")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # STEP 1: Preluare produse principale
        status_text.text("📥 Preluare produse WooCommerce...")
        
        all_items = []
        page = 1
        per_page = 100
        endpoint = f"{woo_url}/wp-json/wc/v3/products"
        
        products_data = []
        while True:
            try:
                response = requests.get(
                    endpoint,
                    auth=(woo_key, woo_secret),
                    params={"per_page": per_page, "page": page, "status": "publish"},
                    timeout=30
                )
                
                if response.status_code != 200:
                    st.error(f"Eroare HTTP {response.status_code}")
                    break
                
                products = response.json()
                if not products:
                    break
                
                products_data.extend(products)
                status_text.text(f"📥 Pagina {page}: {len(products_data)} produse...")
                page += 1
                time.sleep(0.1)
                
            except Exception as e:
                st.error(f"Eroare: {e}")
                break
        
        progress_bar.progress(0.3)
        
        # Separare simple vs variabile
        simple_products = [p for p in products_data if p.get('type') in ['simple', 'external', 'grouped']]
        variable_products = [p for p in products_data if p.get('type') == 'variable']
        
        st.info(f"📦 Produse simple: {len(simple_products)} | Produse variabile: {len(variable_products)}")
        
        all_items.extend(simple_products)
        
        # STEP 2: Preluare variații
        if variable_products:
            status_text.text(f"🔄 Preluare variații pentru {len(variable_products)} produse...")
            total_variations = 0
            
            for idx, var_product in enumerate(variable_products, 1):
                product_id = var_product['id']
                var_page = 1
                
                while True:
                    try:
                        var_endpoint = f"{woo_url}/wp-json/wc/v3/products/{product_id}/variations"
                        var_response = requests.get(
                            var_endpoint,
                            auth=(woo_key, woo_secret),
                            params={"per_page": 100, "page": var_page},
                            timeout=30
                        )
                        
                        if var_response.status_code != 200:
                            break
                        
                        variations = var_response.json()
                        if not variations:
                            break
                        
                        all_items.extend(variations)
                        total_variations += len(variations)
                        var_page += 1
                        time.sleep(0.05)
                        
                    except:
                        break
                
                if idx % 20 == 0 or idx == len(variable_products):
                    status_text.text(f"🔄 Variații: {idx}/{len(variable_products)} produse ({total_variations} variații)")
                    progress = 0.3 + (0.4 * (idx / len(variable_products)))
                    progress_bar.progress(progress)
        
        progress_bar.progress(0.7)
        st.success(f"✅ Total preluat: {len(all_items)} produse (simple + variații)")
        
        # STEP 3: Procesare și pregătire date
        status_text.text("💾 Procesare date...")
        
        stock_data = []
        new_products = []
        
        for product in all_items:
            sku = product.get('sku', '').strip()
            if not sku:
                continue
            
            name = product.get('name', '')
            stock_qty = product.get('stock_quantity')
            stock_qty = float(stock_qty) if stock_qty is not None else 0
            stock_status = product.get('stock_status', 'outofstock')
            product_type = product.get('type', 'unknown')
            product_id = product.get('id', 0)
            
            stock_data.append({
                'sku': sku,
                'stock_quantity': stock_qty,
                'stock_status': stock_status,
                'product_type': product_type,
                'woo_product_id': product_id,
                'last_synced_at': datetime.now().isoformat()
            })
            
            new_products.append({
                'sku': sku,
                'name': name,
                'name_norm': name.lower().strip()
            })
        
        progress_bar.progress(0.8)
        
        # STEP 4: Verifică SKU-uri existente
        status_text.text("🔍 Verificare SKU-uri existente...")
        
        try:
            result = supabase_client.table('product_sku').select('sku').execute()
            existing_skus = {row['sku'] for row in result.data}
        except:
            existing_skus = set()
        
        truly_new_products = [p for p in new_products if p['sku'] not in existing_skus]
        
        # STEP 5: Insert produse noi
        if truly_new_products:
            status_text.text(f"📝 Inserare {len(truly_new_products)} produse noi...")
            
            inserted_count = 0
            batch_size = 50
            
            for i in range(0, len(truly_new_products), batch_size):
                batch = truly_new_products[i:i+batch_size]
                
                try:
                    product_data = [{'name': p['name'], 'name_norm': p['name_norm']} for p in batch]
                    result = supabase_client.table('product').insert(product_data).execute()
                    
                    if result.data:
                        for idx, row in enumerate(result.data):
                            product_id = row['id']
                            sku = batch[idx]['sku']
                            
                            try:
                                supabase_client.table('product_sku').insert({
                                    'product_id': product_id,
                                    'sku': sku,
                                    'is_primary': True
                                }).execute()
                                inserted_count += 1
                            except:
                                pass
                except:
                    pass
            
            st.success(f"✅ Inserate {inserted_count} produse noi")
        
        progress_bar.progress(0.9)
        
        # STEP 6: Upsert stocuri
        status_text.text(f"💾 Actualizare {len(stock_data)} stocuri...")
        
        upserted_count = 0
        batch_size = 500
        
        for i in range(0, len(stock_data), batch_size):
            batch = stock_data[i:i+batch_size]
            
            try:
                supabase_client.table('woocommerce_stock').upsert(batch).execute()
                upserted_count += len(batch)
            except Exception as e:
                st.error(f"Eroare batch {i//batch_size + 1}: {e}")
        
        progress_bar.progress(1.0)
        status_text.empty()
        progress_bar.empty()
        
        st.success(f"✅ Sincronizare completă! Actualizate {upserted_count} stocuri")
        st.markdown("---")
        
        return True

# ====================== FUNCȚII RAPORTARE ======================

def get_woocommerce_stock_from_supabase(supabase_client):
    """Citește stocuri WooCommerce din Supabase"""
    try:
        result = supabase_client.table('woocommerce_stock').select('*').execute()
        
        woo_dict = {}
        for row in result.data:
            sku = row['sku']
            woo_dict[sku] = {
                'stock': float(row.get('stock_quantity', 0)),
                'status': row.get('stock_status', 'outofstock'),
                'type': row.get('product_type', 'unknown'),
                'last_synced': row.get('last_synced_at', '')
            }
        
        return woo_dict
    except Exception as e:
        st.error(f"Eroare Supabase: {e}")
        return {}

def get_smartbill_stocks(email, token, cif, warehouse_name):
    """Preia stocuri direct din SmartBill API"""
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
        
        response = requests.get(url, auth=auth, headers=headers, params=params, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Eroare SmartBill: {response.status_code}")
            with st.expander("Detalii eroare"):
                st.code(response.text)
            return None
            
    except Exception as e:
        st.error(f"Eroare SmartBill: {e}")
        return None

def process_smartbill_data(data):
    """Procesează date SmartBill"""
    sb_dict = {}
    
    if not data:
        return sb_dict
    
    products = []
    
    if isinstance(data, dict) and "list" in data:
        for warehouse_item in data["list"]:
            if isinstance(warehouse_item, dict) and "products" in warehouse_item:
                products.extend(warehouse_item["products"])
    elif isinstance(data, list):
        products = data
    
    for product in products:
        if not isinstance(product, dict):
            continue
            
        code = product.get('productCode', '').strip()
        name = product.get('productName', '').strip()
        quantity = product.get('quantity', 0)
        
        try:
            quantity = float(quantity) if quantity else 0
        except:
            quantity = 0
        
        if code:
            sb_dict[code] = {
                'name': name,
                'stock': quantity
            }
    
    return sb_dict

def generate_discrepancy_report(sb_dict, woo_dict):
    """Generează raport discrepanțe"""
    discrepancies = []
    
    # 1. În SmartBill cu stoc > 0 dar lipsă din WooCommerce
    for code, sb_info in sb_dict.items():
        if code not in woo_dict and sb_info['stock'] > 0:
            discrepancies.append({
                'SKU': code,
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
                'SKU': code,
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
                'SKU': code,
                'Denumire': sb_dict[code]['name'],
                'Stoc SmartBill': sb_stock,
                'Stoc WooCommerce': woo_stock,
                'Diferență': round(diff, 2),
                'Tip': '🔄 Diferență cantitate',
                'Status': 'SINCRONIZARE',
                'Prioritate': 3
            })
    
    # 4. În WooCommerce dar nu în SmartBill
    for code, woo_info in woo_dict.items():
        if code not in sb_dict and woo_info['stock'] > 0:
            discrepancies.append({
                'SKU': code,
                'Denumire': 'N/A',
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

# ====================== UI PRINCIPAL ======================

st.title("📦 Verificare Stoc: SmartBill vs WooCommerce")
st.markdown("---")

# Info ultima sincronizare
if supabase:
    try:
        result = supabase.table('woocommerce_stock').select('last_synced_at').order('last_synced_at', desc=True).limit(1).execute()
        if result.data:
            last_sync = result.data[0]['last_synced_at']
            st.info(f"📅 Ultima sincronizare WooCommerce: {last_sync}")
    except:
        pass

st.markdown("---")

# Butoane principale
col1, col2, col3 = st.columns([1, 1, 2])

with col1:
    sync_button = st.button("🔄 Sincronizare WooCommerce", type="secondary", use_container_width=True)

with col2:
    report_button = st.button("📊 Generează Raport", type="primary", use_container_width=True)

# LOGICA SINCRONIZARE
if sync_button:
    if not supabase:
        st.error("⚠️ Configurează Supabase în sidebar!")
    elif not all([woo_url, woo_key, woo_secret]):
        st.error("⚠️ Configurează WooCommerce în sidebar!")
    else:
        sync_woocommerce_to_supabase(woo_url, woo_key, woo_secret, supabase)

# LOGICA RAPORTARE
if report_button:
    if not supabase:
        st.error("⚠️ Configurează Supabase în sidebar!")
    elif not all([sb_email, sb_token, sb_cif]):
        st.error("⚠️ Configurează SmartBill în sidebar!")
    else:
        start_time = datetime.now()
        
        st.markdown("---")
        st.subheader("📊 Generare Raport")
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            with st.spinner("📥 Citire stocuri WooCommerce..."):
                woo_dict = get_woocommerce_stock_from_supabase(supabase)
            
            if woo_dict:
                st.success(f"✅ WooCommerce: {len(woo_dict)} produse")
            else:
                st.error("❌ Eroare citire WooCommerce")
                st.stop()
        
        with col_b:
            with st.spinner("📥 Preluare SmartBill..."):
                sb_data = get_smartbill_stocks(sb_email, sb_token, sb_cif, WAREHOUSE_NAME)
            
            if sb_data:
                sb_dict = process_smartbill_data(sb_data)
                st.success(f"✅ SmartBill: {len(sb_dict)} produse")
            else:
                st.error("❌ Eroare SmartBill")
                st.stop()
        
        elapsed = (datetime.now() - start_time).total_seconds()
        st.info(f"⏱️ Timp: {elapsed:.1f}s")
        
        st.markdown("---")
        
        # Generare raport
        df_report = generate_discrepancy_report(sb_dict, woo_dict)
        
        if len(df_report) > 0:
            st.header("📊 Raport Discrepanțe")
            
            # Metrici
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.metric("🔴 Critice", len(df_report[df_report['Status'] == 'CRITIC']))
            with m2:
                st.metric("🟡 Atenție", len(df_report[df_report['Status'] == 'ATENTIE']))
            with m3:
                st.metric("🔵 Sincronizare", len(df_report[df_report['Status'] == 'SINCRONIZARE']))
            with m4:
                st.metric("📝 Total", len(df_report))
            
            st.markdown("---")
            
            # Filtre
            f1, f2 = st.columns([1, 2])
            with f1:
                status_filter = st.multiselect(
                    "Status",
                    options=df_report['Status'].unique(),
                    default=df_report['Status'].unique()
                )
            with f2:
                search = st.text_input("🔎 Caută")
            
            df_filtered = df_report[df_report['Status'].isin(status_filter)]
            
            if search:
                mask = (
                    df_filtered['SKU'].astype(str).str.contains(search, case=False, na=False) |
                    df_filtered['Denumire'].astype(str).str.contains(search, case=False, na=False)
                )
                df_filtered = df_filtered[mask]
            
            st.dataframe(df_filtered, use_container_width=True, height=450, hide_index=True)
            st.caption(f"Afișate {len(df_filtered)} din {len(df_report)}")
            
            # Export
            e1, e2, e3 = st.columns([2, 1, 1])
            with e2:
                csv = df_filtered.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    "📥 CSV",
                    data=csv,
                    file_name=f"raport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            with e3:
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
