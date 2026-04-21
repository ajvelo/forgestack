#!/usr/bin/env bash
# Scripted demo of a forgestack session. Deterministic, offline, no API calls.
# Run via: ./examples/demo.sh
# For a recording: asciinema rec -c "./examples/demo.sh" forgestack.cast

set -u

# --- colours ---
R="\033[0m"
B="\033[1m"
D="\033[2m"
CY="\033[36m"
BL="\033[34m"
GR="\033[32m"
YE="\033[33m"
MA="\033[35m"
RD="\033[31m"

p() { printf "%b\n" "$1"; }
pause() { sleep "${1:-0.4}"; }

clear
p ""

# --- CLI banner ---
pause 0.2
p "${D}\$ forgestack run --repo my-app --task code_improvement \"Refactor the cart store to use immutable updates\"${R}"
pause 0.6

# --- session panel ---
p ""
p "${CY}╭───────────────────────────── ${B}⚡ ForgeStack Session${R}${CY} ──────────────────────────────╮${R}"
p "${CY}│${R}                                                                                 ${CY}│${R}"
p "${CY}│${R}  ${D}Session ID:${R} 7c8a4d12-f9e3-4b5a-9c61-0e2a8b6d4f17                            ${CY}│${R}"
p "${CY}│${R}                                                                                 ${CY}│${R}"
p "${CY}╰─────────────────────────────────────────────────────────────────────────────────╯${R}"
pause 0.5

# --- setup ---
p ""
p "${B}${BL}━━━ Setup ━━━${R}"
pause 0.2
p "${D}→${R} Resolving repository..."
pause 0.3
p "  ${GR}✓${R} /Users/developer/code/my-app"
pause 0.2
p "${D}→${R} Gathering codebase context..."
pause 0.4
p "  ${D}Discovering related repos...${R}"
pause 0.6
p "  ${D}Found 2 related repos${R}"
p "  ${GR}✓${R} Context gathered"
pause 0.2
p "${D}→${R} Loading design system context..."
pause 0.3
p "  ${GR}✓${R} Design system loaded"
pause 0.2
p "${D}→${R} Initializing MCP tools..."
pause 0.4
p "  ${GR}✓${R} Loaded 4 MCP tools"
pause 0.5

# --- critique loop ---
p ""
p "${B}${BL}━━━ Critique Loop ━━━${R}"
pause 0.3
p ""
p "${B}Round 1/3${R}"
pause 0.2
p "  ${D}Generator working...${R}"
pause 0.9
p "  ${GR}✓${R} Proposal drafted ${D}(1,842 tokens)${R}"
pause 0.3
p "  ${D}Critic evaluating...${R}"
pause 0.9
p "  ${GR}✓${R} Scored:"
p "    - Correctness:     8.5 / 10"
pause 0.1
p "    - Architecture:    7.5 / 10"
pause 0.1
p "    - Code quality:    8.0 / 10"
pause 0.1
p "    - Completeness:    7.0 / 10"
pause 0.1
p "    - Risk:            8.0 / 10"
p "    ${D}─────────────────────────${R}"
p "    ${B}Final score:       7.8 / 10${R}   ${YE}(threshold 8.5 — revising)${R}"
pause 0.4
p ""
p "  ${D}Critic feedback (summary):${R}"
p "  ${D}- Proposed reducer keeps a nested mutable \`items\` map; tests already${R}"
p "  ${D}  depend on reference equality — switch to a shallow-cloned record.${R}"
p "  ${D}- Missing memoisation boundary for the derived \`cartTotal\` selector.${R}"
p "  ${D}- No migration note for existing persisted state in localStorage.${R}"
pause 0.6

# --- round 2 ---
p ""
p "${B}Round 2/3${R}"
pause 0.2
p "  ${D}Generator working (revising with feedback)...${R}"
pause 1.0
p "  ${GR}✓${R} Revised proposal ${D}(2,104 tokens)${R}"
pause 0.3
p "  ${D}Critic evaluating...${R}"
pause 0.9
p "  ${GR}✓${R} Scored:"
p "    - Correctness:     9.0 / 10  ${GR}(↑ +0.5: reference equality fixed)${R}"
pause 0.1
p "    - Architecture:    8.5 / 10  ${GR}(↑ +1.0: memoisation layer added)${R}"
pause 0.1
p "    - Code quality:    8.5 / 10  ${GR}(↑ +0.5)${R}"
pause 0.1
p "    - Completeness:    8.5 / 10  ${GR}(↑ +1.5: migration path documented)${R}"
pause 0.1
p "    - Risk:            8.5 / 10  ${GR}(↑ +0.5)${R}"
p "    ${D}─────────────────────────${R}"
p "    ${B}Final score:       8.6 / 10${R}   ${GR}✓ Consensus reached${R}"
pause 0.6

# --- synthesis ---
p ""
p "${B}${BL}━━━ Synthesis ━━━${R}"
pause 0.3
p "${D}Synthesizer working...${R}"
pause 1.2
p "${GR}✓${R} Final output produced ${D}(3,287 tokens)${R}"
pause 0.4

p ""
p "${B}Session complete.${R}"
p "  Final score:   ${B}${GR}8.6 / 10${R}"
p "  Rounds used:   2 / 3"
p "  Consensus:     ${GR}✓ passed${R}"
p "  Output saved:  ${B}output/forgestack-7c8a4d12.md${R}"
pause 0.8

# --- post-session quick commands ---
p ""
p "${D}\$ forgestack history --last 3${R}"
pause 0.3
p "${D}┌──────────┬────────────┬──────────────────┬───────┬────────┐${R}"
p "${D}│${R} ID       ${D}│${R} Repo       ${D}│${R} Task             ${D}│${R} Score ${D}│${R} Rounds ${D}│${R}"
p "${D}├──────────┼────────────┼──────────────────┼───────┼────────┤${R}"
p "${D}│${R} 7c8a4d12 ${D}│${R} my-app     ${D}│${R} code_improvement ${D}│${R}  ${GR}0.86${R} ${D}│${R}      2 ${D}│${R}"
p "${D}│${R} 4e1b2fa7 ${D}│${R} my-app     ${D}│${R} feature          ${D}│${R}  ${GR}0.88${R} ${D}│${R}      2 ${D}│${R}"
p "${D}│${R} 90cf3e21 ${D}│${R} my-library ${D}│${R} exploration      ${D}│${R}  ${GR}0.91${R} ${D}│${R}      1 ${D}│${R}"
p "${D}└──────────┴────────────┴──────────────────┴───────┴────────┘${R}"
pause 0.8

p ""
p "${D}\$ forgestack apply output/forgestack-7c8a4d12.md --dry-run${R}"
pause 0.3
p "${B}ForgeStack apply${R} ${D}— dry run${R}"
p "${D}───────────────────────────────────────────────────────${R}"
p "Files to modify:  2"
pause 0.1
p "  - ${CY}src/stores/cart.ts${R}                          ${D}(modify)${R}"
p "  - ${CY}src/stores/selectors.ts${R}                     ${D}(create)${R}"
p "Files to create:  1"
pause 0.1
p "  - ${CY}src/stores/migrations/001_cart_shape.ts${R}     ${D}(create)${R}"
p ""
p "${YE}No changes written (dry run). Run without --dry-run to apply.${R}"
pause 0.8

p ""
