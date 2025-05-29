#!/bin/bash
# filepath: /home/ludvigse/deepracer-custom-car/utils/check_package_sources.sh

# Description: Check which apt repositories installed packages came from
# This helps identify unused repositories that can be safely removed

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

print_warning() {
    echo -e "${YELLOW}Warning: $1${NC}"
}

print_error() {
    echo -e "${RED}Error: $1${NC}"
}

print_success() {
    echo -e "${GREEN}$1${NC}"
}

# Check if running as root (needed for some operations)
if [[ $EUID -eq 0 ]]; then
    print_warning "Running as root. This script can be run as a regular user."
fi

print_header "Analyzing installed packages and their sources"

# Create temporary files
TEMP_DIR=$(mktemp -d)
INSTALLED_PACKAGES="$TEMP_DIR/installed_packages.txt"
PACKAGE_SOURCES="$TEMP_DIR/package_sources.txt"
REPO_SUMMARY="$TEMP_DIR/repo_summary.txt"

# Get list of installed packages
echo "Gathering installed packages..."
dpkg-query -W -f='${Package}\t${Status}\n' | grep "install ok installed" | cut -f1 > "$INSTALLED_PACKAGES"

echo "Analyzing package sources..."

# Function to get package source information
analyze_package_sources() {
    local total_packages=$(wc -l < "$INSTALLED_PACKAGES")
    local count=0
    
    while read -r package; do
        count=$((count + 1))
        if ((count % 100 == 0)); then
            echo "Processed $count/$total_packages packages..."
        fi
        
        # Get the source of the package
        source_info=$(apt-cache policy "$package" 2>/dev/null | grep -A 1 "\*\*\*" | tail -1 | awk '{print $2}' || echo "unknown")
        
        # Get more detailed information
        detailed_info=$(apt-cache policy "$package" 2>/dev/null | grep -A 1 "\*\*\*" | tail -1 || echo "unknown source")
        
        echo -e "$package\t$source_info\t$detailed_info" >> "$PACKAGE_SOURCES"
    done < "$INSTALLED_PACKAGES"
}

analyze_package_sources

print_header "Repository Usage Summary"

# Count packages per repository
echo "Counting packages per repository..."
awk -F'\t' '{print $2}' "$PACKAGE_SOURCES" | sort | uniq -c | sort -nr > "$REPO_SUMMARY"

echo -e "${GREEN}Repository\t\t\tPackage Count${NC}"
echo "----------------------------------------"
while read -r count repo; do
    printf "%-40s %s\n" "$repo" "$count"
done < "$REPO_SUMMARY"

print_header "Detailed Package Breakdown by Repository"

# Show packages grouped by repository
current_repo=""
while IFS=$'\t' read -r package repo detailed; do
    if [[ "$repo" != "$current_repo" ]]; then
        echo -e "\n${YELLOW}=== Repository: $repo ===${NC}"
        current_repo="$repo"
    fi
    echo "  $package"
done < <(sort -k2 "$PACKAGE_SOURCES")

print_header "Active Repository Sources"

echo "Current /etc/apt/sources.list:"
if [[ -f /etc/apt/sources.list ]]; then
    grep -v "^#" /etc/apt/sources.list | grep -v "^$" || echo "No active sources in main file"
else
    echo "No /etc/apt/sources.list file found"
fi

echo -e "\nAdditional sources in /etc/apt/sources.list.d/:"
if [[ -d /etc/apt/sources.list.d ]]; then
    for file in /etc/apt/sources.list.d/*.list; do
        if [[ -f "$file" ]]; then
            echo -e "\n${BLUE}File: $(basename "$file")${NC}"
            grep -v "^#" "$file" | grep -v "^$" || echo "  No active sources"
        fi
    done
else
    echo "No /etc/apt/sources.list.d/ directory found"
fi

print_header "Potentially Unused Repositories"

echo "Checking for repositories with no installed packages..."
# Get all configured repositories - improved parsing
all_repos=$(mktemp)
{
    # Parse /etc/apt/sources.list
    if [[ -f /etc/apt/sources.list ]]; then
        grep -v "^#" /etc/apt/sources.list | grep -v "^$" | while read -r line; do
            # Skip lines with architecture specifications and extract URL
            if [[ "$line" =~ ^deb[[:space:]] ]]; then
                # Remove 'deb ' or 'deb-src ', handle [arch=...] specifications
                url=$(echo "$line" | sed 's/^deb[[:space:]]*\(\[.*\][[:space:]]*\)\?//' | awk '{print $1}')
                echo "$url"
            fi
        done
    fi
    
    # Parse files in /etc/apt/sources.list.d/
    if [[ -d /etc/apt/sources.list.d ]]; then
        find /etc/apt/sources.list.d/ -name "*.list" -exec grep -v "^#" {} \; 2>/dev/null | grep -v "^$" | while read -r line; do
            if [[ "$line" =~ ^deb[[:space:]] ]]; then
                # Remove 'deb ' or 'deb-src ', handle [arch=...] specifications
                url=$(echo "$line" | sed 's/^deb[[:space:]]*\(\[.*\][[:space:]]*\)\?//' | awk '{print $1}')
                echo "$url"
            fi
        done
    fi
} | sort -u > "$all_repos"

used_repos=$(awk -F'\t' '{print $2}' "$PACKAGE_SOURCES" | sort -u)

echo -e "${YELLOW}Repositories that might be unused:${NC}"
while read -r repo; do
    if ! echo "$used_repos" | grep -qF "$repo"; then
        echo "  $repo"
    fi
done < "$all_repos"

print_header "Commands to Remove Unused Repositories"

echo -e "${YELLOW}To remove unused PPAs (Personal Package Archives):${NC}"
echo "sudo apt-add-repository --remove ppa:REPOSITORY_NAME"
echo ""
echo -e "${YELLOW}To remove other repositories:${NC}"
echo "Edit /etc/apt/sources.list and /etc/apt/sources.list.d/*.list files"
echo "Comment out or remove unused repository lines"
echo ""
echo -e "${YELLOW}After removing repositories:${NC}"
echo "sudo apt update"

print_header "Summary"

total_packages=$(wc -l < "$INSTALLED_PACKAGES")
unique_repos=$(awk -F'\t' '{print $2}' "$PACKAGE_SOURCES" | sort -u | wc -l)

echo "Total installed packages: $total_packages"
echo "Unique repositories in use: $unique_repos"
echo ""
echo "Detailed results saved to: $TEMP_DIR"
echo "  - Installed packages: $INSTALLED_PACKAGES"
echo "  - Package sources: $PACKAGE_SOURCES"
echo "  - Repository summary: $REPO_SUMMARY"

print_warning "Always backup your system before removing repositories!"
print_warning "Some packages might show 'unknown' source if they were installed manually or from removed repositories."

# Cleanup option
echo ""
read -p "Remove temporary files? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$TEMP_DIR"
    echo "Temporary files removed."
else
    echo "Temporary files kept in: $TEMP_DIR"
fi