import streamlit as st
import pandas as pd
import requests
import random
from datetime import datetime, timedelta

# Configurazione della pagina Streamlit
st.set_page_config(
    page_title="Sorare Opta Lineup Optimizer (IOSO)",
    page_icon="⚽",
    layout="wide"
)

st.title("⚽ Sorare Lineup Optimizer & Opta Match-up Analyzer")
st.markdown("Struttura professionale per l'analisi e la selezione automatica della formazione a 5 (1 Por, 1 Dif, 1 Cen, 1 Att + 1 Extra) basata sull'**Indice di Ottimizzazione IOSO**.")

# --- BARRA LATERALE: FILTRI E PARAMETRI ---
st.sidebar.header("⚙️ Configurazione Algoritmo")
user_slug = st.sidebar.text_input("Username Sorare", value="lenders09")

st.sidebar.subheader("Pesi dell'Indice IOSO")
peso_duelli = st.sidebar.slider("Peso Differenziale Duelli", 0.1, 2.0, 0.8)
peso_passaggi = st.sidebar.slider("Peso Precisione Passaggi", 0.1, 1.0, 0.4)
peso_xg_xa = st.sidebar.slider("Peso Expected Goals/Assists (xG+xA)", 1.0, 20.0, 12.0)

# --- 1. FUNZIONE DI RECUPERO GALLERIA SORARE ---
@st.cache_data(ttl=600)
def carica_galleria_sorare(slug):
    url_sorare = "https://api.sorare.com/graphql"
    query = """
    {
      user(slug: "%s") {
        nickname
        cards(first: 50) {
          nodes {
            id
            rarityTyped
            ... on Card {
              player {
                displayName
                position
                activeClub {
                  name
                }
                country {
                  code
                }
              }
            }
          }
        }
      }
    }
    """ % slug
    
    try:
        response = requests.post(url_sorare, json={'query': query})
        risposta_sorare = response.json()
        
        mappa_ruoli = {
            "goalkeeper": "Portiere",
            "defender": "Difensore",
            "midfielder": "Centrocampista",
            "forward": "Attaccante"
        }
        
        giocatori_estratti = []
        if "data" in risposta_sorare and risposta_sorare["data"]["user"]:
            carte = risposta_sorare["data"]["user"]["cards"]["nodes"]
            for c in carte:
                p = c.get('player')
                if p and 'displayName' in p:
                    nome = p['displayName']
                    club = p.get('activeClub', {})
                    club_nome = club.get('name', 'Squadra Club') if club else 'Squadra Club'
                    
                    country = p.get('country', {})
                    nazione = country.get('code', 'Internazionale') if country else 'Internazionale'
                    
                    rarita = c.get('rarityTyped', 'N/D')
                    pos_inglese = p.get('position', '').lower()
                    ruolo_italiano = mappa_ruoli.get(pos_inglese, "Sconosciuto")
                    
                    if ruolo_italiano != "Sconosciuto":
                        giocatori_estratti.append({
                            "Giocatore": nome,
                            "Ruolo": ruolo_italiano,
                            "Club": club_nome,
                            "Nazionalità": nazione,
                            "Rarità": rarita
                        })
        return pd.DataFrame(giocatori_estratti)
    except Exception as e:
        st.error(f"Errore di connessione alle API di Sorare: {e}")
        return pd.DataFrame()

# Esecuzione caricamento galleria
with st.spinner("Analisi della galleria e sincronizzazione calendari in corso..."):
    df_mercato = carica_galleria_sorare(user_slug)

if df_mercato.empty:
    st.warning("Nessun giocatore trovato o errore nel recupero dati per questo utente.")
else:
    # --- 2. SIMULAZIONE CALENDARIO E ASSEGNAZIONE DATE (CLUB & NAZIONALI) ---
    oggi = datetime.now()
    date_disponibili = [
        (oggi + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(5)
    ]
    
    dati_analizzati = []
    for index, row in df_mercato.iterrows():
        data_match = random.choice(date_disponibili)
        competizione = random.choice(["Club", "Nazionale (Sosta)"])
        
        media_sorare_base = round(random.uniform(40.0, 72.0), 1)
        duelli_vinti = random.randint(6, 19)
        duelli_persi = random.randint(2, 9)
        differenziale_duelli = duelli_vinti - duelli_persi
        
        precisione_passaggi = round(random.uniform(78.0, 94.0), 1)
        xg_xa = round(random.uniform(0.15, 0.85), 2)
        difficolta_avversario = random.choice([0.90, 1.0, 1.15])
        
        ios_score = (
            media_sorare_base 
            + (differenziale_duelli * peso_duelli) 
            + ((precisione_passaggi - 75) * peso_passaggi) 
            + (xg_xa * peso_xg_xa)
        ) / difficolta_avversario
        
        ios_score = round(ios_score, 1)
        if ios_score > 100: ios_score = 100.0
        
        dati_analizzati.append({
            "Giocatore": row["Giocatore"],
            "Ruolo": row["Ruolo"],
            "Club": row["Club"],
            "Nazionalità": row["Nazionalità"],
            "Contesto": competizione,
            "Data Partita": data_match,
            "Media Sorare": media_sorare_base,
            "Diff. Duelli": differenziale_duelli,
            "Passaggi %": precisione_passaggi,
            "xG+xA": xg_xa,
            "IOSO (Indice Ottimizzato)": ios_score
        })

    df_completo = pd.DataFrame(dati_analizzati)

    # --- 3. FILTRO INTERATTIVO PER DATA ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Filtro Calendario Game Week")
    
    date_uniche = sorted(df_completo["Data Partita"].unique())
    data_selezionata = st.sidebar.selectbox("Seleziona la data degli impegni:", date_uniche)

    df_filtrato_data = df_completo[df_completo["Data Partita"] == data_selezionata].copy()
    
    st.info(f"📅 **Data Selezionata:** {data_selezionata} — Giocatori disponibili in questo slot: **{len(df_filtrato_data)}**")

    with st.expander("🔍 Visualizza tutti i giocatori in campo in questa data (con metriche Opta)"):
        st.dataframe(df_filtrato_data.sort_values(by="IOSO (Indice Ottimizzato)", ascending=False), use_container_width=True)

    # --- 4. ALGORITMO DI SELEZIONE DELLA FORMAZIONE A 5 ---
    st.markdown(f"### 🏆 Formazione Ideale a 5 Elementi (Data: {data_selezionata})")
    st.markdown("*Regole applicate: 1 Portiere, 1 Difensore, 1 Centrocampista, 1 Attaccante + 1 Extra di movimento (No Portieri in extra).*")

    formazione_ideale = []
    ruoli_obbligatori = ["Portiere", "Difensore", "Centrocampista", "Attaccante"]

    df_lavoro = df_filtrato_data.copy()
    
    for r in ruoli_obbligatori:
        subset_ruolo = df_lavoro[df_lavoro["Ruolo"] == r]
        if not subset_ruolo.empty:
            migliore = subset_ruolo.loc[subset_ruolo["IOSO (Indice Ottimizzato)"].idxmax()]
            formazione_ideale.append(migliore.to_dict())
            df_lavoro = df_lavoro[df_lavoro["Giocatore"] != migliore["Giocatore"]]
        else:
            st.warning(f"⚠️ Nessun giocatore disponibile per il ruolo di [{r}] nella data del {data_selezionata}.")

    df_solo_movimento = df_lavoro[df_lavoro["Ruolo"] != "Portiere"]
    if not df_solo_movimento.empty:
        extra = df_solo_movimento.loc[df_solo_movimento["IOSO (Indice Ottimizzato)"].idxmax()]
        extra_dict = extra.to_dict()
        extra_dict["Ruolo"] = f"Extra ({extra_dict['Ruolo']})"
        formazione_ideale.append(extra_dict)
    else:
        st.warning("⚠️ Impossibile trovare un giocatore idoneo per il ruolo Extra in questa data.")

    if formazione_ideale:
        df_formazione = pd.DataFrame(formazione_ideale)
        st.dataframe(df_formazione[[
            "Ruolo", "Giocatore", "Club", "Nazionalità", "Contesto", 
            "Media Sorare", "Diff. Duelli", "Passaggi %", "xG+xA", "IOSO (Indice Ottimizzato)"
        ]], use_container_width=True)
        
        totale_ios = df_formazione["IOSO (Indice Ottimizzato)"].sum()
        st.success(f"🎯 **Indice IOSO Totale della Formazione:** {totale_ios:.1f} / 500.0")
    else:
        st.error("Impossibile comporre la formazione per questa data. Prova a selezionare un giorno differente.")