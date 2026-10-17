"""Shared-value comparisons and a race matrix without hidden campaign intelligence."""
import pygame as pg
from . import alignment
from .races import RACES
from .ui import panel, text, shorten, INK, MUTED, GOLD, CYAN, RED, LINE, PANEL


def shade(value):
    return CYAN if value > 0 else RED if value < 0 else MUTED


def draw(app):
    if app.dialog.get('alignment_matrix'):
        return draw_matrix(app)
    game, owner, surface = app.game, app.dialog['alignment_owner'], app.canvas
    a, b = game.race_id, game._empire(owner).race_id
    report = alignment.relationship(game,'player',owner)
    panel(surface,(230,102,980,706),PANEL,GOLD)
    text(surface,'Why they feel this way',(262,129),30,INK,'title')
    text(surface,shorten(f'{game.empire_name}  /  {game.empire_name_for(owner)}',900,17),(263,177),17,MUTED)
    for x,label,value in ((264,'SHARED VALUES',report.alignment),(574,'HISTORY & ACTIONS',report.history),(884,'OVERALL RELATIONS',report.total)):
        text(surface,label,(x,218),11,MUTED,'mono',1)
        text(surface,f'{value:+}',(x,243),32,shade(value))
    text(surface,'Values + history = overall relations, bounded to −100 … +100.',(264,295),14,MUTED)
    text(surface,'VALUE / −2 TO +2',(264,333),11,GOLD,'mono')
    text(surface,RACES[a].name,(762,331),14,RACES[a].color,right=True)
    text(surface,RACES[b].name,(970,331),14,RACES[b].color,right=True)
    text(surface,'DIFFERENCE',(1175,333),11,GOLD,'mono',right=True)
    av,bv=alignment.PROFILES[a].vector,alignment.PROFILES[b].vector
    for i,(name,poles,va,vb) in enumerate(zip(alignment.AXIS_LABELS,alignment.POLES,av,bv)):
        y=365+i*51
        pg.draw.line(surface,LINE,(264,y-8),(1175,y-8))
        text(surface,name,(264,y),16,INK)
        text(surface,f'{poles[0]}  ↔  {poles[1]}',(264,y+23),12,MUTED)
        text(surface,f'{va:+}',(762,y+7),20,INK,right=True)
        text(surface,f'{vb:+}',(970,y+7),20,INK,right=True)
        text(surface,str(abs(va-vb)),(1175,y+7),20,MUTED,right=True)
    text(surface,f'Total difference {alignment.distance(a,b)} · Fixed reference {alignment.REFERENCE_DISTANCE:.4f} · Alignment {report.alignment:+}',(264,632),16,GOLD)
    text(surface,'Equal weights. Shared values apply once; treaties and conflict change history.',(264,667),14,MUTED)
    text(surface,'A poor match does not prevent agreements. Diplomacy can outweigh shared values.',(264,690),13,MUTED)
    app.button('dialog_alignment_matrix','Race matrix',(264,735,244,43),lambda:app.dialog.update(alignment_matrix=True))
    app.button('dialog_close','Close',(911,735,264,43),app.cancel_dialog,'primary')


def draw_matrix(app):
    surface=app.canvas
    panel(surface,(44,96,1352,713),PANEL,GOLD)
    text(surface,'Shared-values alignment',(75,123),30,INK,'title')
    text(surface,'Race profiles only · positive: affinity · negative: friction · no diplomatic history included',(76,169),15,MUTED)
    races=list(alignment.PROFILES)
    abbreviations=dict(terran='Ter',kharuun='Kha',aelari='Ael',lithar='Lit',varkesh='Var',wanderers='Wan',xenonflora='Xen',nexus='Nex',aetheri='Aeth',concord='Dom',serevan='Ser',skirr='Ski',remnant='Rem')
    labels=[abbreviations[race] for race in races]
    start,step=324,1034/max(1,len(races)-1)
    for j,label in enumerate(labels):
        text(surface,label,(start+j*step,223),13,GOLD,'mono',right=True)
    for i,race in enumerate(races):
        y=258+i*30
        pg.draw.line(surface,LINE,(76,y-10),(1363,y-10))
        text(surface,RACES[race].name,(76,y),15,RACES[race].color)
        for j,other in enumerate(races):
            value=alignment.score(race,other)
            text(surface,'—' if i==j else f'{value:+}',(start+j*step,y),16,shade(value) if i!=j else MUTED,'mono',right=True)
    text(surface,f'Fixed reference difference: {alignment.REFERENCE_DISTANCE:.4f} · Maximum modifier: ±{alignment.MAX_MODIFIER}',(76,674),14,MUTED)
    text(surface,'The same pair keeps the same alignment, regardless of which other races inhabit the galaxy.',(76,700),13,MUTED)
    if 'alignment_owner' in app.dialog:
        app.button('dialog_alignment_compare','← Relationship',(76,747,244,40),lambda:app.dialog.update(alignment_matrix=False))
    app.button('dialog_close','Close',(1110,747,250,40),app.cancel_dialog,'primary')
