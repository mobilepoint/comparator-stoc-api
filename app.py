"""
Aplicație Streamlit - Verificare Stoc SmartBill vs WooCommerce
Cu debug pentru SKU-uri duplicate și deduplicare automată
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

# ====================== FUNCȚII PRINCIPALE ======================

def update_stocks_only(woo_url, woo_key, woo_secret, supabase_client):
    """Update rapid stocuri - cu deduplicare"""
    st.markdown("---")
    st.subheader("⚡ Update Rapid Stocuri")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text("📥 Citire SKU-uri...")
    
    try:
        result = supabase_client.table('woocommerce_stock').select('sku').execute()
        existing_skus = {row['sku'] for row in result.data}
        st.info(f"📦 {len(existing_skus)} SKU-uri în DB")
    except Exception as e:
        st.error(f"Eroare: {e}")
        return False
    
    progress_bar.progress(0.2)
    status_text.text("📥 Preluare stocuri WooCommerce...")
    
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
            
            status_text.text(f"📥 {len(stock_dict)} SKU-uri...")
            page += 1
            time.sleep(0.1)
        except:
            break
    
    stock_updates = list(stock_dict.values())
    
    progress_bar.progress(0.8)
    
    if stock_updates:
        status_text.text(f"💾 Actualizare {len(stock_updates)}...")
        updated = 0
        
        for i in range(0, len(stock_updates), 500):
            batch = stock_updates[i:i+500]
            try:
                supabase_client.table('woocommerce_stock').upsert(batch).execute()
                updated += len(batch)
            except Exception as e:
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

def sync_woocommerce_full(woo_url, woo_key, woo_secret, supabase_client):
    """Sync complet cu deduplicare"""
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
    st.success(f"✅ {len(all_items)} produse preluate")
    
    status_text.text("💾 Procesare și deduplicare...")
    
    # DEDUPLICARE
    stock_dict = {}
    new_products_dict = {}
    
    for p in all_items:
        sku = p.get('sku', '').strip()
        if not sku:
            continue
        
        stock_dict[sku] = {
            'sku': sku,
            'stock_quantity': float(p.get('stock_quantity') or 0),
            'stock_status': p.get('stock_status', 'outofstock'),
            'product_type': p.get('type', 'unknown'),
            'woo_product_id': p.get('id', 0),
            'last_synced_at': datetime.now().isoformat()
        }
        
        new_products_dict[sku] = {
            'sku': sku,
            'name': p.get('name', ''),
            'name_norm': p.get('name', '').lower().strip()
        }
    
    stock_data = list(stock_dict.values())
    new_products = list(new_products_dict.values())
    
    duplicates = len(all_items) - len(stock_data)
    if duplicates > 0:
        st.warning(f"⚠️ {duplicates} SKU-uri duplicate eliminate automat")
    
    progress_bar.progress(0.8)
    
    try:
        result = supabase_client.schema('catalog').table('product_sku').select('sku').execute()
        existing_skus = {row['sku'] for row in result.data}
    except:
        existing_skus = set()
    
    truly_new = [p for p in new_products if p['sku'] not in existing_skus]
    
    if truly_new:
        status_text.text(f"📝 {len(truly_new)} produse noi...")
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
            st.success(f"✅ {inserted} produse noi adăugate")
    
    progress_bar.progress(0.9)
    
    status_text.text(f"💾 {len(stock_data)} stocuri...")
    upserted = 0
    
    for i in range(0, len(stock_data), 500):
        batch = stock_data[i:i+500]
        try:
            supabase_client.table('woocommerce_stock').upsert(batch).execute()
            upserted += len(batch)
        except Exception as e:
            st.warning(f"⚠️ Batch {i//500+1} eșuat, reîncerc individual...")
            for item in batch:
                try:
                    supabase_client.table('woocommerce_stock').upsert([item]).execute()
                    upserted += 1
                except:
                    pass
    
    progress_bar.progress(1.0)
    status_text.empty()
    progress_bar.empty()
    st.success(f"✅ {upserted} stocuri sincronizate")
    return True

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
    """Procesează date SmartBill"""
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
    """Generează raport discrepanțe"""
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

# ====================== FUNCȚIE DEBUG ======================

def debug_find_duplicates(woo_url, woo_key, woo_secret):
    """Debug: Găsește SKU-uri duplicate în WooCommerce"""
    
    st.markdown("---")
    st.subheader("🐛 Debug: Căutare SKU-uri Duplicate")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text("📥 Preluare TOATE produsele...")
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
            status_text.text(f"📥 Produse: {len(products_data)}...")
            page += 1
            time.sleep(0.1)
        except:
            break
    
    progress_bar.progress(0.4)
    
    simple = [p for p in products_data if p.get('type') in ['simple', 'external', 'grouped']]
    variable = [p for p in products_data if p.get('type') == 'variable']
    
    st.info(f"📦 Simple: {len(simple)} | Variabile: {len(variable)}")
    all_items.extend(simple)
    
    if variable:
        status_text.text("🔄 Preluare variații...")
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
                status_text.text(f"🔄 Variații: {idx}/{len(variable)} ({total_var})")
                progress_bar.progress(0.4 + (0.5 * (idx / len(variable))))
    
    progress_bar.progress(0.9)
    st.success(f"✅ Total preluat: {len(all_items)} produse")
    
    status_text.text("🔍 Analiză duplicate...")
    
    sku_map = {}
    skus_empty = 0
    
    for item in all_items:
        sku = item.get('sku', '').strip()
        
        if not sku:
            skus_empty += 1
            continue
        
        if sku not in sku_map:
            sku_map[sku] = []
        
        sku_map[sku].append({
            'id': item.get('id'),
            'name': item.get('name', 'N/A'),
            'type': item.get('type', 'unknown'),
            'stock': item.get('stock_quantity'),
        })
    
    duplicates = {sku: prods for sku, prods in sku_map.items() if len(prods) > 1}
    
    progress_bar.progress(1.0)
    status_text.empty()
    progress_bar.empty()
    
    st.markdown("---")
    st.header("📊 Rezultate Analiză")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total produse", len(all_items))
    c2.metric("SKU-uri unice", len(sku_map))
    c3.metric("🔴 Duplicate", len(duplicates))
    c4.metric("Fără SKU", skus_empty)
    
    if duplicates:
        st.markdown("---")
        st.subheader(f"🔴 {len(duplicates)} SKU-uri Duplicate Găsite")
        
        dup_rows = []
        for sku, prods in duplicates.items():
            for idx, p in enumerate(prods, 1):
                dup_rows.append({
                    'SKU': sku,
                    'Ocurență': f"{idx}/{len(prods)}",
                    'Product ID': p['id'],
                    'Denumire': p['name'][:60] + ('...' if len(p['name']) > 60 else ''),
                    'Tip': p['type'],
                    'Stoc': p['stock'] if p['stock'] is not None else 'N/A'
                })
        
        df = pd.DataFrame(dup_rows).sort_values('SKU')
        st.dataframe(df, use_container_width=True, height=400, hide_index=True)
        
        st.markdown("---")
        st.subheader("📈 Statistici")
        
        dup_counts = {}
        for sku, prods in duplicates.items():
            count = len(prods)
            if count not in dup_counts:
                dup_counts[count] = 0
            dup_counts[count] += 1
        
        for count in sorted(dup_counts.keys()):
            st.write(f"- **{dup_counts[count]} SKU-uri** apar de **{count} ori**")
        
        st.markdown("---")
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "📥 Descarcă Lista Duplicate (CSV)",
            data=csv,
            file_name=f"duplicate_skus_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
        with st.expander("💡 Cum rezolv duplicate?"):
            st.markdown("""
            **În WooCommerce:**
            - Products → All Products → Sortează după SKU
            - Caută SKU-urile din listă
            - Șterge sau modifică duplicate
            
            **În această aplicație:**
            - Deduplicarea automată păstrează ultimul produs cu fiecare SKU
            - La sincronizare, duplicate-le sunt eliminate automat
            """)
    
    else:
        st.success("🎉 Nu există SKU-uri duplicate!")
        st.balloons()
    
    if skus_empty > 0:
        st.markdown("---")
        st.warning(f"⚠️ {skus_empty} produse fără SKU")

# ====================== UI PRINCIPAL ======================

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

# Butoane principale
c1, c2, c3 = st.columns(3)

with c1:
    quick = st.button("⚡ Update Rapid", type="primary", use_container_width=True, help="~2 minute")
with c2:
    full = st.button("🔄 Sync Complet", type="secondary", use_container_width=True, help="~30 minute")
with c3:
    report = st.button("📊 Raport", type="secondary", use_container_width=True)

# Logica butoane principale
if quick:
    if not supabase or not all([woo_url, woo_key, woo_secret]):
        st.error("⚠️ Configurează credențialele!")
    else:
        update_stocks_only(woo_url, woo_key, woo_secret, supabase)

if full:
    if not supabase or not all([woo_url, woo_key, woo_secret]):
        st.error("⚠️ Configurează credențialele!")
    else:
        sync_woocommerce_full(woo_url, woo_key, woo_secret, supabase)

if report:
    if not supabase or not all([sb_email, sb_token, sb_cif]):
        st.error("⚠️ Configurează credențialele!")
    else:
        st.markdown("---")
        with st.spinner("📥 Preluare date..."):
            woo_dict = get_woocommerce_stock_from_supabase(supabase)
            sb_data = get_smartbill_stocks(sb_email, sb_token, sb_cif, WAREHOUSE_NAME)
        
        if woo_dict and sb_data:
            sb_dict = process_smartbill_data(sb_data)
            st.success(f"✅ WooCommerce: {len(woo_dict)} | SmartBill: {len(sb_dict)}")
            df = generate_discrepancy_report(sb_dict, woo_dict)
            
            if len(df) > 0:
                st.header("📊 Raport Discrepanțe")
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("🔴 Critice", len(df[df['Status'] == 'CRITIC']))
                m2.metric("🟡 Atenție", len(df[df['Status'] == 'ATENTIE']))
                m3.metric("🔵 Sincronizare", len(df[df['Status'] == 'SYNC']))
                m4.metric("📝 Total", len(df))
                
                st.markdown("---")
                
                f1, f2 = st.columns([1, 2])
                with f1:
                    status_filter = st.multiselect("Status", df['Status'].unique(), df['Status'].unique())
                with f2:
                    search = st.text_input("🔎 Caută")
                
                df_filt = df[df['Status'].isin(status_filter)]
                if search:
                    df_filt = df_filt[
                        df_filt['SKU'].astype(str).str.contains(search, case=False, na=False) |
                        df_filt['Denumire'].astype(str).str.contains(search, case=False, na=False)
                    ]
                
                st.dataframe(df_filt, use_container_width=True, height=450, hide_index=True)
                st.caption(f"Afișate {len(df_filt)} din {len(df)}")
                
                csv = df_filt.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 Descarcă CSV", csv, f"raport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv", use_container_width=True)
            else:
                st.success("🎉 Nu există discrepanțe!")
                st.balloons()

# Buton debug
st.markdown("---")
st.subheader("🛠️ Tools")

if st.button("🐛 Debug: Caută SKU-uri Duplicate", use_container_width=True, help="Identifică SKU-uri duplicate în WooCommerce"):
    if not all([woo_url, woo_key, woo_secret]):
        st.error("⚠️ Configurează WooCommerce!")
    else:
        debug_find_duplicates(woo_url, woo_key, woo_secret)
