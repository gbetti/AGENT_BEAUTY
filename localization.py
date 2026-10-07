"""Reviewed campaign translations; unknown custom copy fails instead of leaking Italian."""
from copy import deepcopy

LANGUAGES = ('it', 'fr', 'en', 'zh')
COPY = {
'Team incarnato naturale?': ('Team teint naturel ?', 'Team natural complexion?', '偏爱自然肤色？'),
'Il glow è tuo': ('À vous l’éclat', 'Your glow, your way', '绽放你的光彩'),
'Fai spazio al glow': ('Place à l’éclat', 'Make room for glow', '让光彩成为日常'),
'Il tuo rituale glow': ('Votre rituel éclat', 'Your glow ritual', '你的焕亮仪式'),
'Glow: trova il tuo': ('Trouvez votre éclat', 'Find your glow', '发现你的光彩'),
'Sguardo: cambia il rituale': ('Changez de rituel regard', 'Refresh your eye ritual', '焕新眼周护理'),
'Il tuo rituale occhi': ('Votre rituel regard', 'Your eye care ritual', '你的眼周护理仪式'),
'Rughe? Parti dal rituale': ('Rides? Adoptez un rituel', 'Wrinkles? Start your ritual', '淡纹，从日常护理开始'),
'Il tuo sguardo, protagonista': ('Place à votre regard', 'Let your eyes shine', '让双眸成为焦点'),
'Pelle soda? Inizia qui': ('Fermeté : commencez ici', 'Firmer skin? Start here', '紧致肌肤，从这里开始'),
'Dai spazio alla cura': ('Place au soin', 'Make time for care', '留点时间呵护肌肤'),
'Il tuo prossimo rituale': ('Votre prochain rituel', 'Your next skincare ritual', '开启你的护肤仪式'),
'La tua pausa anti-age': ('Votre pause anti-âge', 'Your age-care moment', '你的抗老护理时刻'),
'Scopri il tuo glow': ('Révélez votre éclat', 'Discover your glow', '探索焕亮护理'),
'Scopri il rituale': ('Découvrez le rituel', 'Discover the ritual', '探索护肤仪式'),
'Scopri il prodotto': ('Découvrez le produit', 'Discover the product', '了解产品'),
'Un incarnato luminoso': ('Un teint lumineux', 'A radiant complexion', '焕亮自然肤色'),
'Nutre in profondità': ('Nourrit en profondeur', 'Deeply nourishes', '深层滋养'),
'Leviga le rughe': ('Lisse les rides', 'Smooths wrinkles', '抚平皱纹'),
'Un incarnato luminoso, dalla coprenza naturale.': ('Un teint lumineux, avec une couvrance naturelle.', 'A radiant complexion with natural-looking coverage.', '焕亮肤色，呈现自然遮盖效果。'),
'Leviga rughe e linee sottili del contorno occhi.': ('Lisse les rides et les ridules du contour des yeux.', 'Smooths wrinkles and fine lines around the eyes.', '抚平眼周皱纹与细纹。'),
'Nutre la pelle in profondità. Per una pelle più soda.': ('Nourrit la peau en profondeur. Pour une peau plus ferme.', 'Deeply nourishes the skin. For firmer skin.', '深层滋养肌肤，令肌肤更加紧致。'),
}
ANGLES = {
'natural_glow': ('Place au teint naturel et à l’éclat dans votre rituel beauté.', 'Make natural-looking radiance part of your beauty ritual.', '让自然光彩融入日常护肤。'),
'kbeauty_ritual': ('Les rituels K-beauty nous inspirent à prendre le temps du soin quotidien.', 'K-beauty rituals inspire us to make time for daily skincare.', '从韩式护肤仪式中汲取灵感，为日常护理留出时间。'),
'hydration': ('Hydratation et barrière cutanée inspirent une pause dédiée au soin.', 'Hydration and the skin barrier inspire a moment of daily care.', '从保湿与肌肤屏障话题出发，开启日常护理时刻。'),
'renewal': ('Faites de votre rituel de soin un rendez-vous quotidien.', 'Make your skincare ritual a daily moment for yourself.', '让肌肤护理成为每天留给自己的时光。'),
'beauty_ritual': ('Une inspiration pour votre prochain rituel beauté.', 'Inspiration for your next beauty ritual.', '为下一次护肤仪式寻找灵感。'),
}
ACTIONS = {
'commenti': ('Votre rituel, le matin ou le soir ? Dites-le-nous en commentaire.', 'Morning or evening ritual? Tell us in the comments.', '你的护肤仪式在早晨还是晚上？欢迎留言分享。'),
'salvataggi': ('Enregistrez ce post pour votre prochain rituel.', 'Save this post for your next skincare ritual.', '收藏这篇帖子，为下次护肤留点灵感。'),
'clic': ('Envie de l’intégrer à votre rituel ? Découvrez le produit.', 'Ready to add it to your routine? Discover the product.', '想把它加入日常护理？了解产品详情。'),
}

def translate(value, language):
    if language == 'it': return value
    if value not in COPY:
        raise ValueError('Traduzione mancante per '+language+': '+value)
    return COPY[value][LANGUAGES.index(language)-1]

def localize(creative, product, language):
    if language not in LANGUAGES: raise ValueError('Lingua non supportata: '+language)
    result=deepcopy(creative)
    result['language']=language
    if language=='it': return result
    index=LANGUAGES.index(language)-1
    for key in ('headline','cta','claim'): result[key]=translate(creative[key],language)
    result['angle']=ANGLES[creative['trend_id']][index]
    action=ACTIONS[creative['objective']][index]
    if creative['objective']=='commenti' and product['data']['editorial']['theme']=='glow':
        action=('Team éclat naturel ? Dites-le-nous en commentaire.', 'Love a natural glow? Tell us in the comments.', '喜欢自然光泽？欢迎留言分享。')[index]
    result['caption']='\n\n'.join((result['headline'],result['angle'],product['name']+'\n'+result['claim'],action))
    result['hashtags']=['#IOMAParis']+list((('#SoinVisage','#RituelBeauté','#Éclat'),('#Skincare','#BeautyRitual','#NaturalGlow'),('#护肤','#护肤仪式','#自然光彩'))[index])
    if product['data']['editorial']['theme']!='glow': result['hashtags']=result['hashtags'][:-1]
    return result
