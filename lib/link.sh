# lib/link.sh — shared installer helpers, sourced by install.sh,
# claude/install.sh and omp/install.sh. Requires $TS (backup timestamp) to be
# set by the caller before either function runs.

# link SOURCE TARGET — create TARGET as a symlink to SOURCE.
#   - existing symlink            -> replaced (idempotent)
#   - existing real file/dir      -> backed up to TARGET.bak-<timestamp>
link() {
    local source="$1" target="$2"
    if [ -L "$target" ]; then
        rm "$target"
    elif [ -e "$target" ]; then
        echo "  Backing up existing $target -> $target.bak-$TS"
        mv "$target" "$target.bak-$TS"
    fi
    ln -s "$source" "$target"
    echo "  $target -> $source"
}

# link_skill SOURCE TARGET — a skill dir normally gets one whole-dir symlink.
# A skill that ships SKILL.omp.md (omp-only) instead gets a real directory of
# per-entry symlinks minus SKILL.omp.md, so this tool never sees it and edits
# to existing entries still go live. The entry list is fixed at install time:
# a NEW top-level entry added to such a skill does not appear until reinstall.
# A previous farm of ours (marker file) is replaced silently.
link_skill() {
    local source="$1" target="$2"
    if [ ! -f "$source/SKILL.omp.md" ]; then
        link "$source" "$target"
        return
    fi
    if [ -L "$target" ]; then
        rm "$target"
    elif [ -d "$target" ] && [ -f "$target/.harness-skill-farm" ]; then
        rm -rf "$target"
    elif [ -e "$target" ]; then
        echo "  Backing up existing $target -> $target.bak-$TS"
        mv "$target" "$target.bak-$TS"
    fi
    mkdir "$target"
    echo "per-entry symlinks into $source, minus SKILL.omp.md" > "$target/.harness-skill-farm"
    local entry
    while IFS= read -r entry; do
        ln -s "$entry" "$target/$(basename "$entry")"
    done < <(find "$source" -mindepth 1 -maxdepth 1 ! -name SKILL.omp.md ! -name __pycache__)
    echo "  $target/ -> $source/* (without SKILL.omp.md)"
}
