"""
Aplicație Streamlit - folosind schema public (default)
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
    
    status_text.text("📥 Citire SKU-uri...")
    
    try:
        result = supabase_client.table('woocommerce_stock').select('sku').execute()
        existing_skus = {row['sku'] for row in result.data}
        st.info(f"📦 {len(existing_skus)} SKU-uri")
    except Exception as e:
        st.error(f"Eroare: {e}")
        return False
    
    progress_bar.progress(0.2)
    status_text.text("📥 Preluare stocuri...")
    
    stock_updates = []
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
                    stock_updates.append({
                        'sku': sku,
                        'stock_quantity': float(p.get('stock_quantity') or 0),
                        'stock_status': p.get('stock_status', 'outofstock'),
                        'last_synced_at': datetime.now().isoformat()
                    })
            
            status_text.text(f"📥 {len(stock_updates)} stocuri...")
            page += 1
            time.sleep(0.1)
        except:
            break
    
    progress_bar.progress(0.8)
    
    if stock_updates:
        status_text.text(f"💾 Actualizare...")
        updated = 0
        
        for i in range(0, len(stock_updates), 500):
            batch = stock_updates[i:i+500]
            try:
                supabase_client.table('woocommerce_stock').upsert(batch).execute()
                updated += len(batch)
            except Exception as e:
                st.error(f"Eroare batch: {e}")
        
        progress_bar.progress(1.0)
        status_text.empty()
        progress_bar.empty()
        st.success(f"✅ {updated} stocuri actualizate")
        return True
    
    return False

def sync_woocommerce_full(woo_url, woo_key, woo_secret, supabase_client):
    """Sync complet"""
    st.markdown("---")
    st.subheader("🔄 Sincronizare Completă")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text("📥 Preluare produse...")
    all_items = []
    page = 1
    endpoint = f"{woo_url}/wp-json/wc/v3/products"
    
    products_data = []
    while True:
        try:
            response = requests.get(endpoint, auth=(woo_key, woo_secret), params={"per_page": 100, "page": page, "status": "publish"}, timeout=30)
            if response.status_code != 200:
                break
            products = response.json()
            if not products:
                break
            products_data.extend(products)
            status_text.text(f"📥 {len(products_data)}...")
            page += 1
            time.sleep(0.1)
        except:
            break
    
    progress_bar.progress(0.3)
    
    simple = [p for p in products_data if p.get('type') in ['simple', 'external', 'grouped']]
    variable = [p for p in products_data if p.get('type') == 'variable']
    
    st.info(f"Simple: {len(simple)} | Variabile: {len(variable)}")
    all_items.extend(simple)
    
    if variable:
        status_text.text("🔄 Variații...")
        total_var = 0
        
        for idx, vp in enumerate(variable, 1):
            vpage = 1
            while True:
                try:
                    vr = requests.get(f"{woo_url}/wp-json/wc/v3/products/{vp['id']}/variations", auth=(woo_key, woo_secret), params={"per_page": 100, "page": vpage}, timeout=30)
                    if vr.status_code != 200:
                        break
                    vlist = vr.json()
                    if not vlist:
                        break
                    all_items.extend(vlist)
                    total_var += len(vlist)
                    vpage += 1
                    time.sleep(0.05)
                except:
                    break
            
            if idx % 20 == 0:
                status_text.text(f"🔄 {idx}/{len(variable)} ({total_var})")
                progress_bar.progress(0.3 + (0.4 * (idx / len(variable))))
    
    progress_bar.progress(0.7)
    st.success(f"✅ {len(all_items)}")
    
    status_text.text("💾 Procesare...")
    stock_data = []
    new_products = []
    
    for p in all_items:
        sku = p.get('sku', '').strip()
        if not sku:
            continue
        
        stock_data.append({
            'sku': sku,
            'stock_quantity': float(p.get('stock_quantity') or 0),
            'stock_status': p.get('stock_status', 'outofstock'),
            'product_type': p.get('type', 'unknown'),
            'woo_product_id': p.get('id', 0),
            'last_synced_at': datetime.now().isoformat()
        })
        
        new_products.append({'sku': sku, 'name': p.get('name', ''), 'name_norm': p.get('name', '').lower().strip()})
    
    progress_bar.progress(0.8)
    
    try:
        result = supabase_client.schema('catalog').table('product_sku').select('sku').execute()
        existing_skus = {row['sku'] for row in result.data}
    except:
        existing_skus = set()
    
    truly_new = [p for p in new_products if p['sku'] not in existing_skus]
    
    if truly_new:
        status_text.text(f"📝 {len(truly_new)} noi...")
        inserted = 0
        
        for i in range(0, len(truly_new), 50):
            batch = truly_new[i:i+50]
            try:
                pdata = [{'name': p['name'], 'name_norm': p['name_norm']} for p in batch]
                res = supabase_client.schema('catalog').table('product').insert(pdata).execute()
                
                if res.data:
                    for idx, row in enumerate(res.data):
                        try:
                            supabase_client.schema('catalog').table('product_sku').insert({'product_id': row['id'], 'sku': batch[idx]['sku'], 'is_primary': True}).execute()
                            inserted += 1
                        except:
                            pass
            except:
                pass
        
        if inserted > 0:
            st.success(f"✅ {inserted} produse noi")
    
    progress_bar.progress(0.9)
    
    status_text.text(f"💾 {len(stock_data)}...")
    upserted = 0
    
    for i in range(0, len(stock_data), 500):
        batch = stock_data[i:i+500]
        try:
            supabase_client.table('woocommerce_stock').upsert(batch).execute()
            upserted += len(batch)
        except Exception as e:
            st.error(f"Batch {i//500+1}: {e}")
    
    progress_bar.progress(1.0)
    status_text.empty()
    progress_bar.empty()
    st.success(f"✅ {upserted} stocuri")
    return True

def get_woocommerce_stock_from_supabase(supabase_client):
    try:
        result = supabase_client.table('woocommerce_stock').select('*').execute()
        return {row['sku']: {'stock': float(row.get('stock_quantity', 0)), 'status': row.get('stock_status', 'outofstock')} for row in result.data}
    except Exception as e:
        st.error(f"Eroare: {e}")
        return {}

def get_smartbill_stocks(email, token, cif, warehouse_name):
    try:
        r = requests.get("https://ws.smartbill.ro/SBORO/api/stocks", auth=HTTPBasicAuth(email, token), headers={"Accept": "application/json"}, params={"cif": cif, "date": datetime.now().strftime("%Y-%m-%d"), "warehouseName": warehouse_name}, timeout=30)
        return r.json() if r.status_code == 200 else None
    except:
        return None

def process_smartbill_data(data):
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
    disc = []
    for code, sb in sb_dict.items():
        if code not in woo_dict and sb['stock'] > 0:
            disc.append({'SKU': code, 'Denumire': sb['name'], 'Stoc SB': sb['stock'], 'Stoc Woo': 'N/A', 'Dif': sb['stock'], 'Tip': '❌ Lipsă Woo', 'Status': 'CRITIC', 'P': 1})
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
            st.info(f"📅 {result.data[0]['last_synced_at']}")
    except:
        pass

st.markdown("---")

c1, c2, c3 = st.columns(3)

with c1:
    quick = st.button("⚡ Update", type="primary", use_container_width=True)
with c2:
    full = st.button("🔄 Sync", type="secondary", use_container_width=True)
with c3:
    report = st.button("📊 Raport", type="secondary", use_container_width=True)

if quick:
    if not supabase or not all([woo_url, woo_key, woo_secret]):
        st.error("⚠️ Config!")
    else:
        update_stocks_only(woo_url, woo_key, woo_secret, supabase)

if full:
    if not supabase or not all([woo_url, woo_key, woo_secret]):
        st.error("⚠️ Config!")
    else:
        sync_woocommerce_full(woo_url, woo_key, woo_secret, supabase)

if report:
    if not supabase or not all([sb_email, sb_token, sb_cif]):
        st.error("⚠️ Config!")
    else:
        st.markdown("---")
        with st.spinner("📥..."):
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
