def resolve_vc_spots(params, start, end, fetch_ptax):
    """
    Resolve cotacoes da ponta VC.

    A cotacao inicial pode ser uma cotacao contratada/cliente e nao deve ser
    sobrescrita por PTAX automatica. A busca automatica preenche apenas a
    cotacao final de mercado.
    """
    spot_start = params["spot_start"]

    if params.get("auto_ptax"):
        spot_end = fetch_ptax(end)
    else:
        spot_end = params["spot_end"]

    return spot_start, spot_end
