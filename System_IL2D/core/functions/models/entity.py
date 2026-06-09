class Entity:
 def __init__(s,eid,x,y,hp,mp=0,attack=10,defence=0,ai_type=None,immortal=False):s.eid=eid;s.x=x;s.y=y;s.hp=s.max_hp=hp;s.mp=s.max_mp=mp;s.attack=attack;s.defence=defence;s.move_cooldown=0;s.ai_type=ai_type;s.immortal=immortal
 def pos(s):return s.x,s.y