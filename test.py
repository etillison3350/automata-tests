import itertools
import os
import re

from nfa import NFA
import parsing

if __name__ == '__main__':
    for file in os.listdir('./graphs'):
        os.remove('./graphs/' + file)

    # pattern = '(b|ba*a|a(a|b)a*a)*a'
    # pattern = '(((b|(aa)*)*)*)*'
    pattern = 'a(aa)*b*'
    ts = parsing.parse_regex(pattern)

    for n in range(6, 8):
        for ts in parsing.enumerate_regexes('abc', n):
            # print(ts)

            if (2, 2) in itertools.pairwise(ts):
                continue
            # if any(c not in ts for c in 'abc'):
            #     continue
            # if len([t for t in ts if t is not None and t in 'ab']) < 4:
            #     continue

            onfa = parsing.construct_nfa(ts)
            onfa.dump('./graphs', 'onfa', caption='\n/' + parsing.construct_string(ts) + '/')
            empty = NFA(frozenset((0, 1)), frozenset(), {(0, ''): frozenset((1,))}, 0, 1)
            nfa = onfa.to_dfa().minimize().to_nfa()
            nfa = (empty + nfa).union_edges(combiner=parsing.postfix_union_combiner)
            heuristic = lambda state, in_set, out_set: sum(len(sym) for dst, sym in in_set if dst != state) * len(out_set) + \
                                                       sum(len(sym) for src, sym in out_set if src != state) * len(in_set)
            while len(nfa.states) > 2:
                # nfa.dump('./graphs', 'nfa' + str(len(nfa.states)), edge_label=parsing.postfix_edge_label_func)
                # print({state: nfa.in_out_sets(state) for state in nfa.states})
                rip_state = min((state for state in nfa.states if state != nfa.start_state and state != nfa.final_state),
                                key=lambda s: heuristic(s, *nfa.in_out_sets(s)))
                # print(str(len(nfa.states)), rip_state)
                nfa = nfa.rip(rip_state, combiner=parsing.postfix_rip_combiner)
                nfa = nfa.union_edges(combiner=parsing.postfix_union_combiner)
            # for s in (11, 4, 5, 3, 7, 14, 15, 13, 17, 0, 1, 19):
            #     nfa = nfa.rip(s, combiner=parsing.postfix_rip_combiner).union_edges(combiner=parsing.postfix_union_combiner)
            # nfa.dump('./graphs', 'nfa' + str(len(nfa.states)), edge_label=parsing.postfix_edge_label_func)

            # nfa.dump( './graphs')
            dfa = onfa.to_dfa()
            dfa.dump('./graphs', caption='\n/' + parsing.construct_string(ts) + '/')
            mdfa = dfa.minimize()
            mdfa.dump('./graphs', 'mdfa', caption='\n/' + parsing.construct_string(ts) + '/')
            # dfa.to_nfa().dump('./graphs', 'nfa2')
            # exit(0)

            regex_string = parsing.construct_string(ts)
            # print('/' + regex_string + '/')

            new_regex = parsing.construct_string(next(iter(nfa.transitions))[1])
            # print('/' + new_regex + '/')

            for n in range(min(len(nfa.transitions), len(mdfa.transitions)) + 2):
                for seq in itertools.product(onfa.alphabet, repeat=n):
                    st = ''.join(seq)
                    re_match = re.fullmatch(regex_string, st) is not None
                    new_match = re.fullmatch(new_regex, st) is not None
                    nfa_acc = onfa.accept(st)
                    dfa_acc = mdfa.accept(st)
                    if re_match != nfa_acc or dfa_acc != re_match or re_match != new_match:
                        print(st, '/' + regex_string + '/', re_match, new_match, nfa_acc, dfa_acc)
                        onfa.dump('./graphs', 'onfa')
                        mdfa.dump('./graphs', 'mdfa')
                        exit(1)

    # pattern = '(b|ba*a|a(a|b)a*a)*a'
    # ts = parse_regex(pattern)
    # # ts = parse_regex('a|bc+|de?f*')
    # # ts = parse_regex('(ab)?')
    # print(ts)



    # for state in s[0].states:
    #     print(state, s[0].states_eps_reachable_from(state), s[0].next(state, 'a'), s[0].next(state, 'b'))

    # x = NFA(frozenset(range(4)),
    #         {
    #             (0, 'a'): frozenset((1, 2)),
    #             (1, 'b'): frozenset((1,)),
    #             (1, None): frozenset((2,)),
    #             (2, 'b'): frozenset((2,)),
    #             (2, 'a'): frozenset((3,))
    #         },
    #         0,
    #         frozenset((3,)))
    # x.dump('.')