import itertools
import math
from collections import defaultdict

from nfa import NFA

import random


# Reference: Robert A. Wagner. 1974. Order-n correction for regular languages. Commun. ACM 17, 5 (May 1974), 265–268.
# DOI:https://doi.org/10.1145/360980.360995


def distance_table(nfa: NFA, string: str) -> dict[int, list[tuple[int | float, ...]]]:
    path_lengths: dict[tuple[int, int], tuple[float, float]] = {}
    # eps_lengths: dict[tuple[int, int], float] = {}
    included_syms = defaultdict(bool)
    for start in nfa.states:
        for end in nfa.states:
            if (start, '') in nfa.transitions and end in nfa.transitions[start, '']:
                path_lengths[start, end] = (0, 1)
            else:
                for sym in nfa.alphabet:
                    if (start, sym) in nfa.transitions and end in nfa.transitions[start, sym]:
                        path_lengths[start, end] = (1, 0)
                        included_syms[start, end, sym] = True
                path_lengths.setdefault((start, end), (math.inf, math.inf))
    for k in nfa.states:
        new_path_lengths = {}
        new_included_syms = {}
        for start in nfa.states:
            for end in nfa.states:
                current = path_lengths[start, end]
                thru_k = (path_lengths[start, k][0] + path_lengths[k, end][0],
                          path_lengths[start, k][1] + path_lengths[k, end][1])
                new_path_lengths[start, end] = min(current, thru_k)
                for sym in nfa.alphabet:
                    if current[0] < thru_k[0] or (math.isinf(current[0]) and math.isinf(thru_k[0])):
                        new_included_syms[start, end, sym] = included_syms[start, end, sym]
                    elif current[0] > thru_k[0]:
                        new_included_syms[start, end, sym] = included_syms[start, k, sym] or included_syms[k, end, sym]
                    else:
                        new_included_syms[start, end, sym] = included_syms[start, end, sym] or \
                                                             included_syms[start, k, sym] or included_syms[k, end, sym]
        path_lengths = new_path_lengths
        included_syms = new_included_syms

    print('   ', end='')
    for end in nfa.states:
        print('{:>2d}'.format(end), end=' ')
    print()
    for start in nfa.states:
        print('{:>2d}'.format(start), end=' ')
        for end in nfa.states:
            if math.isinf(path_lengths[start, end][0]):
                print(' . ', end='')
            else:
                print('{:>2.0f}'.format(path_lengths[start, end][0]), end=' ')
        print()
    # print(included_syms)

    table: dict[int, list[tuple[int | float, ..., int]]]
    table = {state: [(0 if state == nfa.start_state else path_lengths[nfa.start_state, state][0],
                      nfa.start_state)]
             for state in nfa.states}

    for ln, sym in enumerate(string):
        for state in nfa.states:
            min_val = (math.inf, math.inf)
            for src in nfa.states:
                prev_cost = table[src][ln][0]
                if path_lengths[src, state][0] == 0:
                    edge_cost = 1
                else:
                    edge_cost = path_lengths[src, state][0] - included_syms.setdefault((src, state, sym), False)
                # if src == state and edge_cost > 1:
                #     edge_cost = 1

                # print('{:>2d} -> {:>2d} = {:>3.0f} + {:>3.0f}; {:>3.0f}/{:>3.0f}'.format(src, state, prev_cost, edge_cost, eps_lengths[nfa.start_state, src], eps_lengths[src, state]))

                min_val = min(min_val, (prev_cost + edge_cost,
                                        src))
            table[state].append(min_val)
        # print()

    print(' ' * 10, end='')
    for sym in string:
        print('{:>6}'.format(sym), end=' ')
    print()
    for state in nfa.states:
        print('{}S{:<2d}{}'.format('>' if state == nfa.final_state else ' ',
                                   state,
                                   '>' if state == nfa.start_state else ' '), end=' ')
        for i in range(len(table[state])):
            if math.isinf(table[state][i][0]):
                print('   -  ', end=' ')
            else:
                print('{:>2.0f},S{:<2d}'.format(table[state][i][0], table[state][i][-1]), end=' ')
        print()
    print()

    transitions = ''
    curr_state = nfa.final_state
    for i in range(len(table[nfa.final_state]) - 1, -1, -1):
        transitions = '{:>6.0f}  '.format(table[curr_state][i][0]) + transitions
        curr_state = table[curr_state][i][-1]
    transitions = '\n' + transitions
    curr_state = nfa.final_state
    for i in range(len(table[nfa.final_state]) - 1, -1, -1):
        transitions = ' --> S{:<2d}'.format(curr_state) + transitions
        curr_state = table[curr_state][i][-1]
    transitions = 'S{:<2d}'.format(curr_state) + transitions
    print('             ' + '       '.join(string) + '\n' + transitions)

    return table


def update_nfa(nfa: NFA, string: str) -> NFA:
    table = distance_table(nfa, string)

    nfa.alphabet.update(string)

    curr_state = nfa.final_state
    for i in range(len(table[nfa.final_state]) - 1, -1, -1):
        prev_state = table[curr_state][i][-1]
        new = True  # table[curr_state][i][3]
        if new:
            nfa.transitions[prev_state, '' if i == 0 else string[i - 1]].add(curr_state)
        print(prev_state, curr_state, string[i - 1], new)
        curr_state = prev_state

    return nfa


import parsing


if __name__ == '__main__':
    inp = """2-5 z: zzztvz
2-8 d: pddzddkdvqgxndd
4-14 r: rrrjrrrrrrbrrccrr
2-7 r: zrgsnrr
9-10 z: zzzxwzznpd
8-13 g: gggggggxgggghggg
1-6 c: xcccxcccccz
3-4 b: bxbt
8-11 d: dddddddzddv
4-14 m: kxdmmmdmfwmmmdfr
16-17 g: ggggggggggggggggg
2-3 f: ddvdlff
9-11 g: ggggpfgggggg
7-8 c: fdhctccc
3-6 c: tmcdcncqcvccg
2-3 l: clllll
1-9 b: bbbbbbbbbb
10-15 w: wglmwwwrnnzgwhhwvvd
10-14 g: ggggggxsgggqggg
9-19 q: fjlqbvtdngwvtbnsgfm""".splitlines()

    nfa = parsing.parse_regex_as_nfa(inp[0], use_eps=True)  # .to_dfa().minimize().to_nfa()
    nfa.dump('./graphs')
    for string in inp[1:2]:
        update_nfa(nfa, string)
        if not nfa.accept(string):
            nfa.dump('./graphs', 'nnfa')
            assert False
    nfa.dump('./graphs', 'nnfa')
    nfa.to_dfa().minimize().dump('./graphs', 'ndfa')
