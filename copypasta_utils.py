import copypasta_data

PRON_M = "he"
PRON_F = "she"
PRON_N = "they"
PRON_T = "it"

PRON_OPTS = [PRON_M, PRON_F, PRON_N, PRON_T]

PRONOUNS = {
    PRON_M: ("he", "him", "his", "he's"),
    PRON_F: ("she", "her", "her", "she's"),
    PRON_N: ("they", "them", "their", "they're"),
    PRON_T: ("it", "it", "its", "it's"),
}

AVAILABLE_PASTAS = list(copypasta_data.copypasta_list.keys())

def fill_copypasta(key, target, pronoun):
    pron, subj_pron, poss_pron, pron_is = PRONOUNS[pronoun]
    return copypasta_data.copypasta_list[key].format(
        target=target, 
        pron=pron, 
        subj_pron=subj_pron, 
        poss_pron=poss_pron, 
        pron_is=pron_is)