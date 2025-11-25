#!/bin/bash
# Simple script to find organization feedback URLs

DATA_DIR="20401_digital_omnibus"
CSV_FILE="$DATA_DIR/feedbacks.csv"
BASE_URL="https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/14855-Simplification-digital-package-and-omnibus/feedback/F"

if [ ! -f "$CSV_FILE" ]; then
    echo "Error: $CSV_FILE not found!"
    echo "Please run the download script first."
    exit 1
fi

echo "Searching for organizations in $CSV_FILE..."
echo ""

# Function to search and format URL
search_org() {
    local org_pattern="$1"
    local org_name="$2"
    
    result=$(grep -i "$org_pattern" "$CSV_FILE" | head -1)
    
    if [ -n "$result" ]; then
        # Extract ID (first column)
        id=$(echo "$result" | cut -d',' -f1)
        exact_name=$(echo "$result" | cut -d',' -f4 | sed 's/"//g')
        country=$(echo "$result" | cut -d',' -f6 | sed 's/"//g')
        
        echo "✓ $org_name"
        echo "  Name: $exact_name"
        echo "  Country: $country"
        echo "  URL: ${BASE_URL}${id}"
        echo ""
    else
        echo "✗ $org_name - NOT FOUND"
        echo ""
    fi
}

# Search for each organization
search_org "Ada Lovelace" "Ada Lovelace Institute"
search_org "Noyb" "Noyb"
search_org "Estonian.*Ministry.*Justice" "Estonian Ministry of Justice and Digital Affairs"
search_org "Chamber.*Munich" "Chamber of Commerce and Industry for Munich and Upper Bavaria"
search_org "Czech Republic" "Government Office of the Czech Republic"
search_org "U\.S\.*Chamber" "U.S. Chamber of Commerce"
search_org "American Chamber.*EU" "American Chamber of Commerce to the EU"
search_org "Japan Business\|JBCE" "Japan Business Council in Europe"
search_org "Uber" "Uber"
search_org "Bolt" "Bolt"
search_org "IBM" "IBM"
search_org "AlgorithmWatch" "AlgorithmWatch"
search_org "TikTok" "TikTok"
search_org "Pour Demain" "Pour Demain"
search_org "Humboldt" "Alexander von Humboldt Institute"
search_org "Alliance.*Responsible.*Data" "Alliance for Responsible Data Collection"
search_org "CIPL\|Centre.*Information.*Policy" "Centre for Information Policy Leadership"
search_org "LinkedIn" "LinkedIn Ireland"
search_org "Hugging Face" "Hugging Face"
search_org "CDT Europe" "CDT Europe"
search_org "SaferAI" "SaferAI"
search_org "Mistral" "Mistral"
search_org "Amazon" "Amazon"
search_org "Google" "Google"
search_org "OpenAI" "OpenAI"
search_org "Meta" "Meta"
search_org "OpenMined" "OpenMined"
