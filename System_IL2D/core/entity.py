class Entity:
    def __init__(self, eid, x, y, hp, mp=0, attack=10, defence=0, ai_type=None, immortal=False):
        self.eid = eid
        self.x = x
        self.y = y
        self.hp = hp
        self.max_hp = hp
        self.mp = mp
        self.max_mp = mp
        self.attack = attack
        self.defence = defence  # 0~100 damage reduction percent
        self.move_cooldown = 0
        self.ai_type = ai_type
        self.immortal = immortal

    def pos(self):
        return (self.x, self.y)
