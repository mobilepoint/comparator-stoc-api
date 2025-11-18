"""
Aplicație Streamlit - Verificare Stoc SmartBill vs WooCommerce
Cu gestionare interactivă duplicate SKU
"""

import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
import time
import io

st.set_page_config(
    page_title="Verificare Stoc SmartBill vs WooCommerce",
    page_icon="📦",
    layout="wide"
)

WAREHOUSE_NAME = "Eroilor 19 cv"

# ====================== SIDEBAR ======================

with st.sidebar:
    st.header("⚙️ Configurări")
    
    st.subheader("🔵 SmartBill")
    try:
        sb_email = st.secrets["smartbill"]["email"]
        sb_token = st.secrets["smartbill"]["token"]
        sb_cif = st.secrets["smartbill"]["cif"]
        st.success("✅ SmartBill")
    except:
        sb_email = st.text_input("Email", value="mobilepointgsm@gmail.com")
        sb_token = st.text_input("Token", type="password")
        sb_cif = st.text_input("CIF", value="RO36898183")
    
    st.markdown("---")
    
    st.subheader("🟢 WooCommerce")
    try:
        woo_url = st.secrets["woocommerce"]["url"]
        woo_key = st.secrets["woocommerce"]["consumer_key"]
        woo_secret = st.secrets["woocommerce"]["consumer_secret"]
        st.success("✅ WooCommerce")
    except:
        woo_url = st.text_input("URL", value="https://servicepack.ro")
        woo_key = st.text_input("Consumer Key", type="password")
        woo_secret = st.text_input("Consumer Secret", type="password")
    
    st.markdown("---")
    
    st.subheader("💾 Supabase")
    try:
        supabase_url = st.secrets["supabase"]["url"]
        supabase_key = st.secrets["supabase"]["key"]
        supabase: Client = create_client(supabase_url, supabase_key)
        st.success("✅ Conectat")
    except:
        supabase_url = st.text_input("Supabase URL")
        supabase_key = st.text_input("Supabase Key", type="password")
        if supabase_url and supabase_key:
            try:
                supabase = create_client(supabase_url, supabase_key)
                st.success("✅ Conectat")
            except:
                st.error("❌ Eroare")
                supabase = None
        else:
            supabase = None

# ====================== FUNCȚII ======================

def update_stocks_only(woo_url, woo_key, woo_secret, supabase_client):
    """Update rapid stocuri"""
    st.markdown("---")
    st.subheader("⚡ Update Rapid Stocuri")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text("📥 Citire SKU-uri din Supabase...")
    
    try:
        result = supabase_client.table('woocommerce_stock').select('sku').execute()
        existing_skus = {row['sku'] for row in result.data}
        st.info(f"📦 {len(existing_skus)} SKU-uri în baza de date")
    except Exception as e:
        st.error(f"Eroare: {e}")
        return False
    
    progress_bar.progress(0.2)
    status_text.text("📥 Preluare stocuri din WooCommerce...")
    
    stock_dict = {}
    page = 1
    endpoint = f"{woo_url}/wp-json/wc/v3/products"
    
    while True:
        try:
            response = requests.get(
                endpoint,
                auth=(woo_key, woo_secret),
                params={"per_page": 100, "page": page, "status": "publish", "_fields": "sku,stock_quantity,stock_status"},
                timeout=30
            )
            
            if response.status_code != 200:
                break
            
            products = response.json()
            if not products:
                break
            
            for p in products:
                sku = p.get('sku', '').strip()
                if sku and sku in existing_skus:
                    stock_dict[sku] = {
                        'sku': sku,
                        'stock_quantity': float(p.get('stock_quantity') or 0),
                        'stock_status': p.get('stock_status', 'outofstock'),
                        'last_synced_at': datetime.now().isoformat()
                    }
            
            status_text.text(f"📥 {len(stock_dict)} stocuri preluate...")
            page += 1
            time.sleep(0.1)
        except:
            break
    
    stock_updates = list(stock_dict.values())
    progress_bar.progress(0.8)
    
    if stock_updates:
        status_text.text(f"💾 Actualizare {len(stock_updates)} stocuri...")
        updated = 0
        
        for i in range(0, len(stock_updates), 500):
            batch = stock_updates[i:i+500]
            try:
                supabase_client.table('woocommerce_stock').upsert(batch).execute()
                updated += len(batch)
            except:
                for item in batch:
                    try:
                        supabase_client.table('woocommerce_stock').upsert([item]).execute()
                        updated += 1
                    except:
                        pass
        
        progress_bar.progress(1.0)
        status_text.empty()
        progress_bar.empty()
        st.success(f"✅ {updated} stocuri actualizate")
        return True
    
    return False

def sync_woocommerce_full_safe(woo_url, woo_key, woo_secret, supabase_client):
    """
    Sincronizare cu detectare și gestionare interactivă duplicate
    """
    st.markdown("---")
    st.subheader("🔄 Sincronizare Completă (Safe Mode)")
    
    # Initialize session state pentru tracking
    if 'sync_sku_map' not in st.session_state:
        st.session_state.sync_sku_map = {}
    if 'sync_products_processed' not in st.session_state:
        st.session_state.sync_products_processed = []
    if 'sync_page' not in st.session_state:
        st.session_state.sync_page = 1
    if 'sync_paused' not in st.session_state:
        st.session_state.sync_paused = False
    if 'sync_duplicate_found' not in st.session_state:
        st.session_state.sync_duplicate_found = None
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Dacă avem un duplicat în așteptare
    if st.session_state.sync_duplicate_found:
        dup = st.session_state.sync_duplicate_found
        
        st.error(f"🔴 DUPLICAT GĂSIT: SKU `{dup['sku']}`")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Produs existent:**")
            st.json({
                'Product ID': dup['existing']['id'],
                'Nume': dup['existing']['name'],
                'Tip': dup['existing']['type'],
                'Stoc': dup['existing']['stock']
            })
        
        with col2:
            st.write("**Produs duplicat:**")
            st.json({
                'Product ID': dup['new']['id'],
                'Nume': dup['new']['name'],
                'Tip': dup['new']['type'],
                'Stoc': dup['new']['stock']
            })
        
        st.markdown("---")
        st.write("### Ce vrei să faci?")
        
        action_col1, action_col2, action_col3 = st.columns(3)
        
        with action_col1:
            if st.button("✅ Păstrează primul (ignoră duplicatul)", use_container_width=True):
                st.session_state.sync_duplicate_found = None
                st.rerun()
        
        with action_col2:
            if st.button("🔄 Înlocuiește cu cel nou", use_container_width=True):
                # Înlocuiește în map
                st.session_state.sync_sku_map[dup['sku']] = dup['new']
                st.session_state.sync_duplicate_found = None
                st.rerun()
        
        with action_col3:
            if st.button("❌ Stop sincronizare", use_container_width=True, type="primary"):
                st.session_state.sync_sku_map = {}
                st.session_state.sync_products_processed = []
                st.session_state.sync_page = 1
                st.session_state.sync_duplicate_found = None
                st.error("Sincronizare oprită manual")
                return False
        
        return None  # Așteaptă decizie user
    
    # Continuă sincronizarea
    status_text.text(f"📥 Preluare produse (pagina {st.session_state.sync_page})...")
    
    endpoint = f"{woo_url}/wp-json/wc/v3/products"
    
    try:
        response = requests.get(
            endpoint,
            auth=(woo_key, woo_secret),
            params={"per_page": 100, "page": st.session_state.sync_page, "status": "publish"},
            timeout=30
        )
        
        if response.status_code != 200:
            st.error(f"Eroare API: {response.status_code}")
            return False
        
        products = response.json()
        
        if not products:
            # Finalizare sincronizare
            st.success(f"✅ Sincronizare completă! {len(st.session_state.sync_sku_map)} produse unice")
            
            # Salvează în Supabase
            status_text.text("💾 Salvare în Supabase...")
            
            stock_data = []
            for sku, prod_data in st.session_state.sync_sku_map.items():
                stock_data.append({
                    'sku': sku,
                    'stock_quantity': float(prod_data['stock']) if prod_data['stock'] is not None else 0,
                    'stock_status': prod_data['status'],
                    'product_type': prod_data['type'],
                    'woo_product_id': prod_data['id'],
                    'last_synced_at': datetime.now().isoformat()
                })
            
            saved = 0
            for i in range(0, len(stock_data), 500):
                batch = stock_data[i:i+500]
                try:
                    supabase_client.table('woocommerce_stock').upsert(batch).execute()
                    saved += len(batch)
                except:
                    for item in batch:
                        try:
                            supabase_client.table('woocommerce_stock').upsert([item]).execute()
                            saved += 1
                        except:
                            pass
            
            st.success(f"✅ {saved} produse salvate în Supabase")
            
            # Reset session state
            st.session_state.sync_sku_map = {}
            st.session_state.sync_products_processed = []
            st.session_state.sync_page = 1
            
            progress_bar.empty()
            status_text.empty()
            return True
        
        # Procesează produsele din pagina curentă
        for product in products:
            sku = product.get('sku', '').strip()
            
            if not sku:
                continue
            
            product_data = {
                'id': product.get('id'),
                'name': product.get('name', 'N/A'),
                'type': product.get('type', 'unknown'),
                'stock': product.get('stock_quantity'),
                'status': product.get('stock_status', 'outofstock')
            }
            
            # Verifică duplicat
            if sku in st.session_state.sync_sku_map:
                # DUPLICAT GĂSIT!
                st.session_state.sync_duplicate_found = {
                    'sku': sku,
                    'existing': st.session_state.sync_sku_map[sku],
                    'new': product_data
                }
                st.rerun()
                return None
            
            # Adaugă produs nou
            st.session_state.sync_sku_map[sku] = product_data
            st.session_state.sync_products_processed.append(product)
        
        # Mergi la următoarea pagină
        st.session_state.sync_page += 1
        
        progress = min(0.1 + (st.session_state.sync_page / 100), 0.9)
        progress_bar.progress(progress)
        status_text.text(f"📥 {len(st.session_state.sync_sku_map)} produse procesate...")
        
        # Trigger rerun pentru următoarea pagină
        time.sleep(0.1)
        st.rerun()
        
    except Exception as e:
        st.error(f"Eroare: {e}")
        return False

def get_woocommerce_stock_from_supabase(supabase_client):
    """Citește stocuri din Supabase"""
    try:
        result = supabase_client.table('woocommerce_stock').select('*').execute()
        return {row['sku']: {'stock': float(row.get('stock_quantity', 0)), 'status': row.get('stock_status', 'outofstock')} for row in result.data}
    except Exception as e:
        st.error(f"Eroare: {e}")
        return {}

def get_smartbill_stocks(email, token, cif, warehouse_name):
    """Preia stocuri SmartBill"""
    try:
        r = requests.get("https://ws.smartbill.ro/SBORO/api/stocks", auth=HTTPBasicAuth(email, token), headers={"Accept": "application/json"}, params={"cif": cif, "date": datetime.now().strftime("%Y-%m-%d"), "warehouseName": warehouse_name}, timeout=30)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def process_smartbill_data(data):
    """Procesează SmartBill"""
    sb_dict = {}
    if not data:
        return sb_dict
    products = []
    if isinstance(data, dict) and "list" in data:
        for w in data["list"]:
            if isinstance(w, dict) and "products" in w:
                products.extend(w["products"])
    for p in products:
        if not isinstance(p, dict):
            continue
        code = p.get('productCode', '').strip()
        if code:
            sb_dict[code] = {'name': p.get('productName', ''), 'stock': float(p.get('quantity', 0))}
    return sb_dict

def generate_discrepancy_report(sb_dict, woo_dict):
    """Generează raport"""
    disc = []
    for code, sb in sb_dict.items():
        if code not in woo_dict and sb['stock'] > 0:
            disc.append({'SKU': code, 'Denumire': sb['name'], 'Stoc SB': sb['stock'], 'Stoc Woo': 'N/A', 'Dif': sb['stock'], 'Tip': '❌ Lipsă', 'Status': 'CRITIC', 'P': 1})
        elif code in woo_dict and sb['stock'] > 0 and woo_dict[code]['stock'] == 0:
            disc.append({'SKU': code, 'Denumire': sb['name'], 'Stoc SB': sb['stock'], 'Stoc Woo': 0, 'Dif': sb['stock'], 'Tip': '⚠️ 0 Woo', 'Status': 'ATENTIE', 'P': 2})
    for code in set(sb_dict.keys()) & set(woo_dict.keys()):
        diff = sb_dict[code]['stock'] - woo_dict[code]['stock']
        if abs(diff) > 0.01:
            disc.append({'SKU': code, 'Denumire': sb_dict[code]['name'], 'Stoc SB': sb_dict[code]['stock'], 'Stoc Woo': woo_dict[code]['stock'], 'Dif': round(diff, 2), 'Tip': '🔄 Dif', 'Status': 'SYNC', 'P': 3})
    for code, woo in woo_dict.items():
        if code not in sb_dict and woo['stock'] > 0:
            disc.append({'SKU': code, 'Denumire': 'N/A', 'Stoc SB': 0, 'Stoc Woo': woo['stock'], 'Dif': -woo['stock'], 'Tip': '🚫 Woo', 'Status': 'CRITIC', 'P': 1})
    df = pd.DataFrame(disc)
    if len(df) > 0:
        df = df.sort_values(['P', 'Stoc SB'], ascending=[True, False]).drop('P', axis=1)
    return df

# ====================== UI ======================

st.title("📦 Stoc: SmartBill vs WooCommerce")
st.markdown("---")

if supabase:
    try:
        result = supabase.table('woocommerce_stock').select('last_synced_at').order('last_synced_at', desc=True).limit(1).execute()
        if result.data:
            st.info(f"📅 Ultima sincronizare: {result.data[0]['last_synced_at']}")
    except:
        pass

st.markdown("---")

c1, c2, c3 = st.columns(3)

with c1:
    quick = st.button("⚡ Update Rapid", type="primary", use_container_width=True, help="~2 min")
with c2:
    full = st.button("🔄 Sync Complet (Safe)", type="secondary", use_container_width=True, help="Cu verificare duplicate")
with c3:
    report = st.button("📊 Raport", type="secondary", use_container_width=True)

if quick:
    if not supabase or not all([woo_url, woo_key, woo_secret]):
        st.error("⚠️ Configurează!")
    else:
        update_stocks_only(woo_url, woo_key, woo_secret, supabase)

if full:
    if not supabase or not all([woo_url, woo_key, woo_secret]):
        st.error("⚠️ Configurează!")
    else:
        sync_woocommerce_full_safe(woo_url, woo_key, woo_secret, supabase)

if report:
    if not supabase or not all([sb_email, sb_token, sb_cif]):
        st.error("⚠️ Configurează!")
    else:
        st.markdown("---")
        with st.spinner("📥 Preluare..."):
            woo_dict = get_woocommerce_stock_from_supabase(supabase)
            sb_data = get_smartbill_stocks(sb_email, sb_token, sb_cif, WAREHOUSE_NAME)
        
        if woo_dict and sb_data:
            sb_dict = process_smartbill_data(sb_data)
            st.success(f"✅ Woo: {len(woo_dict)} | SB: {len(sb_dict)}")
            df = generate_discrepancy_report(sb_dict, woo_dict)
            
            if len(df) > 0:
                st.header("📊 Discrepanțe")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🔴", len(df[df['Status'] == 'CRITIC']))
                m2.metric("🟡", len(df[df['Status'] == 'ATENTIE']))
                m3.metric("🔵", len(df[df['Status'] == 'SYNC']))
                m4.metric("📝", len(df))
                
                st.dataframe(df, use_container_width=True, height=450, hide_index=True)
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 CSV", csv, f"raport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            else:
                st.success("🎉 OK!")
                st.balloons()
