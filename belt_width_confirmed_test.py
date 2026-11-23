from belt_width_assist import BeltSettings,confirmed_site_width,BeltWidthAssist
assert BeltSettings().width_mm==1180
for initial in ({},{'belt_size_width':'1100'},{'belt_size_width':'1200'}):
 state=dict(initial);state['counts']='99';state['belt_size_observe']='1'
 get=lambda k,d:state.get(k,d)
 set_=lambda k,v:state.__setitem__(k,v)
 assert confirmed_site_width(get,set_)==1180
 assert state['counts']=='99' and state['belt_size_observe']=='1'
 state['belt_size_width']='1210'
 assert confirmed_site_width(get,set_)==1210
 state['belt_size_width']='bad'
 assert confirmed_site_width(get,set_)==1180
print('PASS confirmed 1180 default and one-time upgrade; later edits and comparison/count state retained')
