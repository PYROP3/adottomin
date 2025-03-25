try:
    import copypasta_data

    def _and_capitalized(*prons):
        return prons + tuple(pron.capitalize() for pron in prons)

    PRONOUNS = {# pr, subj, poss, to-be, verb-to-be, have
        prons[0]: _and_capitalized(*prons) for prons in [
            ("he", "him", "his", "he's", "is", "has"),
            ("she", "her", "her", "she's", "is", "has"),
            ("they", "them", "their", "they're", "are", "have"),
            ("it", "it", "its", "it's", "is", "has"),
        ]
    }

    PRON_OPTS = list(PRONOUNS.keys())

    AVAILABLE_PASTAS = list(copypasta_data.copypasta_list.keys())

    def fill_copypasta(key, target, pronoun):
        pron, subj_pron, poss_pron, pron_is, verb_to_be, have, Pron, Subj_pron, Poss_pron, Pron_is, Verb_to_be, Have = PRONOUNS[pronoun]
        return copypasta_data.copypasta_list[key].format(
            target=target, 
            pron=pron, 
            subj_pron=subj_pron, 
            poss_pron=poss_pron, 
            pron_is=pron_is,
            verb_to_be=verb_to_be,
            have=have,
            Pron=Pron,
            Subj_pron=Subj_pron,
            Poss_pron=Poss_pron,
            Pron_is=Pron_is,
            Verb_to_be=Verb_to_be,
            Have=Have)
            
except:
    import sys
    print("Copypasta data not found, ignoring...", file=sys.stderr)
    PRON_OPTS = []
    AVAILABLE_PASTAS = []
