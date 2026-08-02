import json
import os
import requests

# 1. Endpoint officiel APIDAE v002 pour les listes
API_URL = "https://api.apidae-tourisme.com/api/v002/recherche/list-objets-touristiques"
API_KEY = os.environ.get("APIDAE_KEY")
PROJECT_ID = os.environ.get("APIDAE_PROJECT_ID")

# 2. Vos 6 sélections d'hébergements (Remplacez les numéros par vos vrais ID Apidae)
CATEGORIES = {
    "hotels": {"id_selection": 188585, "features": []},
    "campings": {"id_selection": 188587, "features": []},
    "chambres_hotes": {"id_selection": 188589, "features": []},
    "gites_etape": {"id_selection": 188586, "features": []},
    "refuges": {"id_selection": 188593, "features": []},
    "villages_vacances": {"id_selection": 188594, "features": []}
}

def clean_html(text):
    if not text: return ""
    return text.replace("<br>", "\n").replace("<br/>", "\n")

def get_adresse(obj):
    """Reconstruit proprement l'adresse selon les champs Apidae V002."""
    adresse_obj = obj.get("adresse", {})
    lignes = adresse_obj.get("adresse1", "")
    if adresse_obj.get("adresse2"):
        lignes += f", {adresse_obj.get('adresse2')}"
    code_postal = adresse_obj.get("commune", {}).get("codePostal", "")
    commune = adresse_obj.get("commune", {}).get("nom", "")
    return f"{lignes} {code_postal} {commune}".strip()

def extract_contacts(obj):
    """Extrait le téléphone, l'email et le site web via les codes V002."""
    tel, email, web = "", "", ""
    communications = obj.get("informations", {}).get("moyensCommunication", [])
    for contact in communications:
        type_com = contact.get("type", {}).get("id")
        valeur = contact.get("coordonnees", {}).get("fr", "")
        if type_com == 201 and not tel: tel = valeur     # Code Standard Téléphone
        elif type_com == 204 and not email: email = valeur # Code Standard Email
        elif type_com == 205 and not web: web = valeur   # Code Standard Site Web
    return tel, email, web

def extract_photo(obj):
    """Extrait l'adresse de l'image principale dans le tableau d'illustrations V002."""
    illustrations = obj.get("illustrations", [])
    if illustrations and len(illustrations) > 0:
        first_illus = illustrations[0] # On prend la première image
        # En v002, l'URL racine de l'image est directement accessible
        if "url" in first_illus:
            return first_illus.get("url", "")
        # Sécurité si elle est cachée dans les métadonnées de traduction
        traduc = first_illus.get("traductionMetadonnees", {})
        if traduc:
            return traduc.get("url", "")
    return ""

def interroger_apidae(id_selection):
    """Envoie la requête au format Form-Data avec le paramètre stringified 'query' requis en V002."""
    query_params = {
        "apiKey": API_KEY,
        "projetId": int(PROJECT_ID),
        "selectionIds": [int(id_selection)],
        "count": 1000 # Récupère jusqu'à 1000 lignes
    }
    
    # RÈGLE V002 : Le JSON doit être converti en chaîne de texte dans la variable 'query'
    payload = {"query": json.dumps(query_params)}
    
    try:
        # data= au lieu de json= pour forcer le format application/x-www-form-urlencoded
        response = requests.post(API_URL, data=payload)
        if response.status_code == 200:
            return response.json().get("objetsTouristiques", [])
        else:
            print(f"Erreur serveur Apidae ({response.status_code}) pour la sélection {id_selection}")
            return []
    except Exception as e:
        print(f"Erreur de connexion sur la sélection {id_selection}: {e}")
        return []

def main():
    if not API_KEY or not PROJECT_ID:
        print("Erreur : Les clés de configuration (Secrets GitHub) sont introuvables.")
        return

    # Boucle sur les 6 sélections
    for name_key, info in CATEGORIES.items():
        print(f"Extraction Apidae V002 -> {name_key} (Sélection {info['id_selection']})...")
        objets = interroger_apidae(info["id_selection"])
        
        for obj in objets:
            # Extraction des coordonnées géographiques de l'hébergement
            geoloc = obj.get("localisation", {}).get("geolocalisation", {})
            geo_json_data = geoloc.get("geoJson", {})
            points = geo_json_data.get("coordinates", [])
            
            # Si pas de coordonnées GPS valides, on ignore pour éviter de faire planter uMap
            if not points or len(points) < 2: 
                continue
                
            nom = obj.get("nom", {}).get("libelleFr", "")
            desc = obj.get("presentation", {}).get("descriptifCourt", {}).get("libelleFr", "")
            adresse = get_adresse(obj)
            tel, email, web = extract_contacts(obj)
            photo = extract_photo(obj)
            
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": points # [Longitude, Latitude]
                },
                "properties": {
                    "nom": nom,
                    "description": clean_html(desc),
                    "adresse": adresse,
                    "telephone": tel,
                    "email": email,
                    "site_web": web,
                    "photo": photo
                }
            }
            info["features"].append(feature)
            
        # Écriture du fichier GeoJSON individuel
        filename = f"{name_key}.geojson"
        geojson_output = {
            "type": "FeatureCollection",
            "features": info["features"]
        }
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(geojson_output, f, ensure_ascii=False, indent=4)
        print(f"Fichier créé avec succès : {filename} ({len(info['features'])} objets).")

if __name__ == "__main__":
    main()
