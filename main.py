import pygame
import sys
import random
import os
import math
import time
import wave
import struct
import json
import tempfile
import threading


###############################################################
# Disaster Commander - 공모전 버전
# 이 파일은 Python + Pygame으로 작성된 단일 게임 파일입니다.
# - 창 크기: 1000 x 700
# - 화면: 시작 / 플레이 / 결과
# - 도시 지도 스타일 배경 (절차적 생성)
# - 시민 아이콘, 재난 위치, 미니맵, 애니메이션, 난이도, 사운드 시스템 포함
# - 코드 길이 ~1000줄 이상, 기능별 클래스로 분리
###############################################################


# 전역 상수
WIDTH, HEIGHT = 1000, 700
FPS = 60

# 게임 상태
STATE_MENU = "menu"
STATE_PLAYING = "playing"
STATE_GAME_OVER = "game_over"


###############################################################
# 사운드 생성 유틸
###############################################################

def create_tone(filename: str, freq: float, duration: float = 0.18) -> str:
    """지정된 주파수의 짧은 톤을 WAV 파일로 생성한다."""
    # Use temp directory to avoid write permission issues
    temp_dir = tempfile.gettempdir()
    temp_filename = os.path.join(temp_dir, filename)
    
    if os.path.exists(temp_filename):
        return temp_filename

    framerate = 44100
    nframes = int(duration * framerate)
    amplitude = 20000

    try:
        # 순수 파이썬 방식으로 샘플을 생성한다. numpy가 없어도 항상 동작한다.
        with wave.open(temp_filename, "w") as wf:
            wf.setparams((1, 2, framerate, nframes, "NONE", "not compressed"))
            chunk_size = 1000
            frames = bytearray()
            for chunk_start in range(0, nframes, chunk_size):
                chunk_end = min(chunk_start + chunk_size, nframes)
                for i in range(chunk_start, chunk_end):
                    t = i / framerate
                    sample = int(amplitude * math.sin(2 * math.pi * freq * t))
                    frames.extend(struct.pack("<h", sample))
            wf.writeframes(bytes(frames))
    except Exception as e:
        print(f"Warning: Failed to generate tone {filename}: {e}")
        # Create silent file as fallback
        with wave.open(temp_filename, "w") as wf:
            wf.setparams((1, 2, framerate, nframes, "NONE", "not compressed"))
            wf.writeframes(b'\x00\x00' * nframes)
    
    return temp_filename


###############################################################
# 버튼 UI 클래스
###############################################################

class Button:
    """
    고급 버튼 UI 컴포넌트.
    - hover 시 밝아짐
    - 클릭 시 살짝 눌리는 애니메이션
    - 그림자 효과
    - 내부 아이콘 표시(선택) 가능
    """

    def __init__(
        self,
        rect,
        text,
        font,
        base_color,
        hover_color,
        text_color=(255, 255, 255),
        icon_surface: pygame.Surface | None = None,
        command_key: str | None = None,
        tooltip: str = "",
    ):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.font = font
        self.base_color = base_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.icon_surface = icon_surface
        self.command_key = command_key
        self.tooltip = tooltip

        # 쿨다운 / 비활성화
        self.cooldown = 0.0
        self.cooldown_max = 0.0
        self.enabled = True

    def set_cooldown(self, seconds: float):
        self.cooldown = seconds
        self.cooldown_max = max(self.cooldown_max, seconds)

    def is_available(self):
        return self.enabled and self.cooldown <= 0.0

    def draw(self, surface, x=None, y=None):
        if x is not None and y is not None:
            self.rect.x = x
            self.rect.y = y
        mouse_pos = pygame.mouse.get_pos()
        mouse_pressed = pygame.mouse.get_pressed()[0]
        is_hover = self.rect.collidepoint(mouse_pos)

        # 버튼 그림자
        shadow_rect = self.rect.copy()
        shadow_rect.move_ip(2, 2)
        pygame.draw.rect(surface, (0, 0, 0, 140), shadow_rect, border_radius=10)

        # hover / press 색상 및 위치 보정
        color = self.base_color
        offset = 0
        if self.cooldown > 0 or not self.enabled:
            color = (80, 80, 80)
        elif is_hover:
            color = self.hover_color
            if mouse_pressed:
                offset = 2  # 눌린 느낌
                color = tuple(max(0, c - 20) for c in color)

        btn_rect = self.rect.copy()
        btn_rect.y += offset

        # 반투명 배경
        btn_surf = pygame.Surface(btn_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(btn_surf, (*color, 240), btn_surf.get_rect(), border_radius=10)
        pygame.draw.rect(btn_surf, (0, 0, 0), btn_surf.get_rect(), 2, border_radius=10)
        surface.blit(btn_surf, btn_rect.topleft)

        # 쿨다운 오버레이
        if self.cooldown > 0:
            ratio = min(1.0, self.cooldown / max(0.001, self.cooldown_max))
            overlay = pygame.Surface(btn_rect.size, pygame.SRCALPHA)
            overlay.fill((10, 10, 10, 160))
            cut = int(btn_rect.height * (1 - ratio))
            pygame.draw.rect(overlay, (0, 0, 0, 180), (0, 0, btn_rect.width, cut))
            surface.blit(overlay, btn_rect.topleft)
            cd_text = self.font.render(f"{int(self.cooldown)+1}", True, (240, 240, 240))
            surface.blit(cd_text, cd_text.get_rect(center=btn_rect.center))

        # 아이콘 + 텍스트 레이아웃
        total_width = 0
        icon_rect = None
        icon_surf = None
        if self.icon_surface:
            icon_size = min(btn_rect.height - 16, 28)
            icon_surf = pygame.transform.smoothscale(self.icon_surface, (icon_size, icon_size))
            icon_rect = icon_surf.get_rect()
            total_width += icon_rect.width + 6

        text_surf = self.font.render(self.text, True, self.text_color)
        total_width += text_surf.get_width()

        start_x = btn_rect.left + (btn_rect.width - total_width) // 2
        center_y = btn_rect.top + btn_rect.height // 2

        if icon_rect and icon_surf:
            icon_rect.topleft = (start_x, center_y - icon_rect.height // 2)
            surface.blit(icon_surf, icon_rect)
            start_x += icon_rect.width + 6

        text_rect = text_surf.get_rect(midleft=(start_x, center_y))
        surface.blit(text_surf, text_rect)

        # Tooltip
        if is_hover and self.tooltip and self.command_key:
            tip_surf = self.font.render(self.tooltip, True, (230, 230, 230))
            tip_bg = tip_surf.get_rect().inflate(12, 8)
            tip_bg.midbottom = (btn_rect.centerx, btn_rect.top - 8)
            tip_bg.x = max(8, min(WIDTH - tip_bg.width - 8, tip_bg.x))
            if tip_bg.y < 8:
                tip_bg.midtop = (btn_rect.centerx, btn_rect.bottom + 8)
                tip_bg.x = max(8, min(WIDTH - tip_bg.width - 8, tip_bg.x))
            pygame.draw.rect(surface, (20, 24, 30, 220), tip_bg, border_radius=6)
            pygame.draw.rect(surface, (140, 140, 160), tip_bg, 1, border_radius=6)
            surface.blit(tip_surf, (tip_bg.x + 6, tip_bg.y + 4))

    def is_clicked(self, event) -> bool:
        return (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.rect.collidepoint(event.pos)
        )


###############################################################
# 재난/시민/헬기/팝업 데이터 구조
###############################################################

class Disaster:
    """재난 정의 정보(타입, 색, 설명, 행동 결과 등)."""

    def __init__(self, name, eng_name, description, color, severity, action_outcomes, type_id):
        self.name = name
        self.eng_name = eng_name
        self.description = description
        self.color = color
        self.severity = severity
        self.action_outcomes = action_outcomes
        self.type_id = type_id


class DisasterInstance:
    """실제 필드에 발생한 개별 재난."""

    def __init__(self, disaster: Disaster, position: pygame.Vector2):
        self.disaster = disaster
        self.position = position
        self.start_time = time.time()
        self.decision_start_time = time.time()
        self.resolved = False
        self.resolved_action = None
        # 홍수/산불 등 확산형 재난의 반경 및 확산 속도
        self.radius = 0.0
        self.spread_speed = 0.0
        # 시각 효과
        self.effect_timer = 0.0
        self.intel_level = 0
        self.evac_ordered = False
        self.traffic_control = False
        # 연쇄 재난 시스템
        self.is_chain_disaster = False
        self.chain_source = None  # 이 재난을 유발한 원본 재난
        self.chain_cooldown = 0.0
        self.fx_particles = []

    def draw(self, surface, offset=(0, 0)):
        if self.resolved:
            return
        ox, oy = offset
        center = (int(self.position.x + ox), int(self.position.y + oy))
        age = max(0.0, time.time() - self.start_time)
        if self.disaster.type_id == "wildfire":
            pulse = (math.sin(time.time() * 8.0) + 1.0) * 0.5
            ring_radius = 18 + int(pulse * 8)
            pygame.draw.circle(surface, (255, 180, 70), center, ring_radius, 3)
            pygame.draw.circle(surface, (255, 95, 20), center, max(8, ring_radius // 2), 2)
            for i in range(10):
                ang = time.time() * 2.5 + i * 0.6
                rr = 12 + (i % 4) * 4
                px = center[0] + math.cos(ang) * rr
                py = center[1] + math.sin(ang * 1.2) * rr * 0.7
                pygame.draw.circle(surface, (255, 140 + i * 10, 0), (int(px), int(py)), 2)
            if age < 1.0:
                for i in range(8):
                    ang = age * 14.0 + i * (math.pi * 2 / 8)
                    rr = 10 + i * 3
                    px = center[0] + math.cos(ang) * rr
                    py = center[1] + math.sin(ang * 1.3) * rr * 0.75
                    pygame.draw.circle(surface, (255, 210, 80), (int(px), int(py)), 2)
        elif self.disaster.type_id == "flood":
            splash_width = 64
            splash_height = 18 + int((math.sin(time.time() * 5.0) + 1.0) * 4)
            splash_rect = pygame.Rect(0, 0, splash_width, splash_height)
            splash_rect.center = center
            pygame.draw.ellipse(surface, (90, 150, 240, 120), splash_rect)
            pygame.draw.ellipse(surface, (170, 220, 255, 110), splash_rect.inflate(18, 10), 2)
            if age < 1.0:
                splash2 = splash_rect.inflate(20, 8)
                pygame.draw.ellipse(surface, (110, 190, 255, 70), splash2, 2)
                pygame.draw.line(surface, (150, 210, 255), (center[0] - 22, center[1]), (center[0] + 22, center[1]), 2)
        elif self.disaster.type_id == "earthquake":
            ring_radius = 20 + int((math.sin(time.time() * 6.0) + 1.0) * 4)
            pygame.draw.circle(surface, (255, 220, 120), center, ring_radius, 2)
            if age < 1.0:
                for i in range(6):
                    ang = age * 10.0 + i * 1.1
                    px = center[0] + math.cos(ang) * (20 + i * 3)
                    py = center[1] + math.sin(ang) * (16 + i * 2)
                    pygame.draw.line(surface, (255, 230, 170), center, (int(px), int(py)), 2)
        # 재난 종류에 따른 시각 효과
        if self.disaster.type_id == "wildfire":
            # 붉은 애니메이션, 연기
            self.effect_timer += 0.1
            for i in range(5):
                angle = self.effect_timer + i * 1.256
                x = self.position.x + math.cos(angle) * 20 + ox
                y = self.position.y + math.sin(angle) * 20 + oy
                pygame.draw.circle(surface, (255, 100 + i*30, 0), (int(x), int(y)), 3)
            # 연기
            for i in range(3):
                x = self.position.x + random.randint(-10, 10) + ox
                y = self.position.y - 20 - i * 10 + oy
                pygame.draw.circle(surface, (100, 100, 100, 150), (x, y), 2)
        elif self.disaster.type_id == "flood":
            # 물 애니메이션, 강 범람
            self.effect_timer += 0.05
            wave_height = math.sin(self.effect_timer) * 5
            pygame.draw.ellipse(surface, (70, 110, 170, 150), (self.position.x - 30 + ox, self.position.y + wave_height - 10 + oy, 60, 20))
        elif self.disaster.type_id == "earthquake":
            # 화면 흔들림은 Game에서 처리, 건물 피해 표시
            if random.random() < 0.1:
                pygame.draw.line(surface, (255, 0, 0), (self.position.x - 10 + ox, self.position.y - 10 + oy), (self.position.x + 10 + ox, self.position.y + 10 + oy), 2)
                pygame.draw.line(surface, (255, 0, 0), (self.position.x + 10 + ox, self.position.y - 10 + oy), (self.position.x - 10 + ox, self.position.y + 10 + oy), 2)


class Citizen:
    """도시 위에 뿌려지는 시민 아이콘."""

    def __init__(self, x: float, y: float):
        self.pos = pygame.Vector2(x, y)
        # 시민 상태: NORMAL / DANGER / INJURED / RESCUED
        self.state = "NORMAL"
        self.alive = True
        self.velocity = pygame.Vector2(0, 0)
        self.wander_timer = 0.0
        self.rescored = False  # 점수 반영 여부 플래그
        self.controlled_by_player = False  # 대피 모드에서 직접 조작 중인지 여부
        # 캐시된 서피스
        self.cached_surface = None
        self.last_color = None

    def draw(self, surface, offset=(0, 0)):
        if not self.alive:
            return
        ox, oy = offset
        color = (236, 236, 236)
        if self.state == "DANGER":
            color = (255, 150, 80)
        elif self.state == "INJURED":
            color = (255, 100, 140)
        elif self.state == "RESCUED":
            color = (120, 220, 140)
        
        # 캐시된 서피스 사용 또는 생성
        if self.cached_surface is None or self.last_color != color:
            alpha = 200
            head_radius = 3
            body_length = 6
            self.cached_surface = pygame.Surface((8, 10), pygame.SRCALPHA)
            pygame.draw.circle(self.cached_surface, (*color, alpha), (4, 3), head_radius)
            pygame.draw.line(self.cached_surface, (*color, alpha), (4, 5), (4, 7), 1)
            self.last_color = color
        
        surface.blit(self.cached_surface, (int(self.pos.x + ox) - 4, int(self.pos.y + oy) - 5))

    def update(self, dt: float, game: "Game"):
        """
        간단한 시민 AI:
        - 평소에는 랜덤 워크
        - 가까운 재난이 있으면 반대 방향으로 이동
        - 구조대가 근처에 있으면 구조대 방향으로 천천히 이동
        - 대피 구역에 들어가면 RESCUED 상태
        """
        if not self.alive:
            return

        if self.controlled_by_player:
            return

        # 이미 구조된 시민은 움직이지 않는다.
        if self.state == "RESCUED":
            return

        base_speed = 40.0
        # 폭설 시 이동 속도 감소
        if game.is_blizzard_active():
            base_speed *= 0.6
        if self.state == "INJURED":
            base_speed *= 0.5

        # 1) 재난 회피
        nearest_dis, nearest_dist = game.get_nearest_active_disaster(self.pos)
        flee_vector = pygame.Vector2(0, 0)
        if nearest_dis and nearest_dist < 160:
            self.state = "DANGER"
            flee_vector = self.pos - nearest_dis.position
            if flee_vector.length() > 0:
                flee_vector = flee_vector.normalize()

        # 2) 재난 시 대피소로 이동
        shelter_vector = pygame.Vector2(0, 0)
        if nearest_dis and nearest_dist < 200:  # 재난 가까이 있으면 대피소로
            shelters = game.evac_zones
            if shelters:
                nearest_shelter = min(shelters, key=lambda b: (self.pos - pygame.Vector2(b.rect.center)).length())
                direction = pygame.Vector2(nearest_shelter.rect.center) - self.pos
                if direction.length() > 0:
                    direction = direction.normalize()
                shelter_vector = direction

        # 3) 구조대 근처면 구조대 쪽으로 조금 이동 시도
        team_vector = pygame.Vector2(0, 0)
        nearest_team, team_dist = game.get_nearest_rescue_team(self.pos)
        if nearest_team and team_dist < 140:
            direction = nearest_team.pos - self.pos
            if direction.length() > 0:
                direction = direction.normalize()
            team_vector = direction

        # 4) 기본 랜덤 워크
        self.wander_timer -= dt
        if self.wander_timer <= 0:
            angle = random.uniform(0, math.pi * 2)
            self.velocity = pygame.Vector2(math.cos(angle), math.sin(angle))
            self.wander_timer = random.uniform(1.0, 3.0)

        move_dir = self.velocity
        if flee_vector.length_squared() > 0:
            move_dir = flee_vector
        elif shelter_vector.length_squared() > 0:
            move_dir = shelter_vector
        elif team_vector.length_squared() > 0:
            move_dir = move_dir * 0.4 + team_vector * 0.6

        if move_dir.length_squared() > 0:
            move_dir = move_dir.normalize()
            new_pos = self.pos + move_dir * base_speed * dt
            # 강을 피해 이동
            if game.is_position_blocked(new_pos):
                # 강을 건너지 않도록 방향을 틀기
                move_dir = pygame.Vector2(-move_dir.y, move_dir.x)
                new_pos = self.pos + move_dir * base_speed * dt
                if game.is_position_blocked(new_pos):
                    new_pos = self.pos
            self.pos = new_pos

        # 화면 경계 제한
        self.pos.x = max(20, min(WIDTH - 280, self.pos.x))
        self.pos.y = max(90, min(HEIGHT - 152, self.pos.y))

        # 대피 구역 도착 체크
        for zone in game.evac_zones:
            if zone.rect.collidepoint(self.pos.x, self.pos.y):
                self.state = "RESCUED"
                break


class RescueTeam:
    """구조대 유닛."""

    def __init__(self, x: float, y: float):
        self.pos = pygame.Vector2(x, y)
        self.speed = 120.0
        self.target_citizen: Citizen | None = None
        self.support_cooldown = 0.0

    def update(self, dt: float, game: "Game"):
        """
        - 가장 가까운 위험/부상 시민을 향해 이동
        - 근처 시민을 구조하여 대피 구역으로 이동시킴
        - 재난 진압
        """
        # 폭설 시 이동 속도 감소
        speed = self.speed * (0.7 if game.is_blizzard_active() else 1.0)
        if self.support_cooldown > 0:
            self.support_cooldown = max(0.0, self.support_cooldown - dt)

        # 타겟 시민이 없거나 이미 사망/구조되었으면 다시 탐색
        if not self.target_citizen or not self.target_citizen.alive or self.target_citizen.state == "RESCUED":
            self.target_citizen = game.get_nearest_danger_citizen(self.pos)

        if self.target_citizen:
            direction = self.target_citizen.pos - self.pos
            dist = direction.length()
            if dist > 4:
                direction = direction.normalize()
                new_pos = self.pos + direction * speed * dt
                if game.is_position_blocked(new_pos):
                    detour = pygame.Vector2(-direction.y, direction.x)
                    new_pos = self.pos + detour * speed * dt
                    if game.is_position_blocked(new_pos):
                        new_pos = self.pos
                self.pos = new_pos

            # 충분히 가까워지면 시민 구조 처리
            if dist < 10:
                game.rescue_citizen(self.target_citizen)
                self.target_citizen = None
        else:
            # 시민이 없으면 재난 주변으로 이동해 현장 지원만 한다.
            nearest_dis, nearest_dist = game.get_nearest_active_disaster(self.pos)
            if nearest_dis and nearest_dist > 10:
                direction = nearest_dis.position - self.pos
                if direction.length() > 0:
                    direction = direction.normalize()
                new_pos = self.pos + direction * speed * dt
                if game.is_position_blocked(new_pos):
                    detour = pygame.Vector2(-direction.y, direction.x)
                    new_pos = self.pos + detour * speed * dt
                    if game.is_position_blocked(new_pos):
                        new_pos = self.pos
                self.pos = new_pos
            elif nearest_dis and nearest_dist <= 10:
                if self.support_cooldown <= 0:
                    game.popup_messages.append(
                        PopupMessage(f"구조대 현장 지원: {nearest_dis.disaster.name}", (120, 220, 255), 1.6)
                    )
                    self.support_cooldown = 2.0

    def draw(self, surface, offset=(0, 0)):
        ox, oy = offset
        # 녹색 원 + 내부 십자
        center = (int(self.pos.x + ox), int(self.pos.y + oy))
        radius = 6
        pygame.draw.circle(surface, (0, 180, 0), center, radius)
        pygame.draw.circle(surface, (0, 0, 0), center, radius, 1)
        # 십자
        cross_size = 3
        pygame.draw.line(surface, (255, 255, 255), (center[0] - cross_size, center[1]), (center[0] + cross_size, center[1]), 1)
        pygame.draw.line(surface, (255, 255, 255), (center[0], center[1] - cross_size), (center[0], center[1] + cross_size), 1)


class Building:
    """도시 건물 / 공원 / 병원 / 경찰서 등을 표현하는 객체."""

    def __init__(self, rect: pygame.Rect, district: str):
        self.rect = rect
        self.district = district  # residential / industrial / park / hospital / police
        self.collapsed = False
        self.on_fire = False
        # 색상 랜덤 적용
        self.color = self.get_base_color()
        self.randomize_color()
        # 캐시된 그림자 서피스
        self.cached_shadow = None
        # 공원 나무 위치 미리 생성
        if self.district == "park":
            tree_count = random.randint(3, 6)
            self.park_trees = [
                (
                    random.randint(self.rect.left + 2, self.rect.right - 2),
                    random.randint(self.rect.top + 2, self.rect.bottom - 2)
                )
                for _ in range(tree_count)
            ]
            self.park_tree_colors = [
                (
                    max(0, min(255, 40 + random.randint(-10, 10))),
                    max(0, min(255, 90 + random.randint(-10, 10))),
                    max(0, min(255, 50 + random.randint(-10, 10))),
                )
                for _ in range(tree_count)
            ]
        else:
            self.park_trees = []
            self.park_tree_colors = []
        
        # 구역별 취약도 시스템
        self.vulnerability = self.get_district_vulnerability()

    def get_base_color(self):
        if self.district == "residential":
            return (180, 200, 220)  # 연한 파랑
        elif self.district == "industrial":
            return (120, 120, 120)  # 회색
        elif self.district == "park":
            return (70, 130, 90)  # 초록
        elif self.district == "hospital":
            return (255, 255, 255)  # 흰색
        elif self.district == "police":
            return (100, 100, 200)  # 파랑
        else:
            return (100, 100, 100)

    def get_district_vulnerability(self) -> dict:
        """구역별 재난 취약도를 반환한다."""
        vulnerability = {
            "flood": 1.0,      # 홍수
            "wildfire": 1.0,   # 산불
            "earthquake": 1.0, # 지진
            "blizzard": 1.0    # 폭설
        }
        
        if self.district == "residential":
            # 주거지: 홍수에 취약, 지진에 보통
            vulnerability["flood"] = 1.5
            vulnerability["earthquake"] = 1.2
        elif self.district == "industrial":
            # 산업지구: 화재에 취약, 지진에 취약
            vulnerability["wildfire"] = 1.8
            vulnerability["earthquake"] = 1.4
        elif self.district == "park":
            # 공원: 산불에 매우 취약
            vulnerability["wildfire"] = 2.0
            vulnerability["flood"] = 0.8
        elif self.district == "hospital":
            # 병원: 모든 재난에 보통, 중요도 높음
            vulnerability = {k: 0.9 for k in vulnerability}
        elif self.district == "police":
            # 경찰서: 지진에 취약
            vulnerability["earthquake"] = 1.3
            
        return vulnerability

    def randomize_color(self):
        # 색상 약간 랜덤 변경
        r, g, b = self.color
        r = max(0, min(255, r + random.randint(-20, 20)))
        g = max(0, min(255, g + random.randint(-20, 20)))
        b = max(0, min(255, b + random.randint(-20, 20)))
        self.color = (r, g, b)

    def draw(self, surface, offset=(0, 0)):
        if self.collapsed:
            return
        ox, oy = offset
        # 캐시된 그림자 사용 또는 생성
        if self.cached_shadow is None:
            shadow_offset = (3, 3)
            shadow_color = (30, 30, 40, 100)
            shadow_rect = self.rect.move(shadow_offset)
            self.cached_shadow = pygame.Surface(shadow_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(self.cached_shadow, shadow_color, self.cached_shadow.get_rect(), border_radius=2)
        
        draw_rect = self.rect.move((ox, oy))
        shadow_rect = draw_rect.move((3, 3))
        surface.blit(self.cached_shadow, shadow_rect.topleft)

        # 건물 본체
        pygame.draw.rect(surface, self.color, draw_rect)
        pygame.draw.rect(surface, (0, 0, 0), draw_rect, 1)

        # 창문 (주거, 산업, 병원, 경찰서)
        if self.district in ["residential", "industrial", "hospital", "police"]:
            window_color = (200, 220, 255) if self.district == "hospital" else (255, 255, 200)
            window_w, window_h = 3, 4
            spacing_x, spacing_y = 6, 6
            for wx in range(draw_rect.left + 2, draw_rect.right - window_w, window_w + spacing_x):
                for wy in range(draw_rect.top + 2, draw_rect.bottom - window_h, window_h + spacing_y):
                    pygame.draw.rect(surface, window_color, (wx, wy, window_w, window_h))
                    pygame.draw.rect(surface, (0, 0, 0), (wx, wy, window_w, window_h), 1)

        if self.district == "hospital":
            # 빨간 십자 표시
            center_x = draw_rect.centerx
            center_y = draw_rect.centery
            cross_size = min(self.rect.width, self.rect.height) // 4
            pygame.draw.line(surface, (255, 0, 0), (center_x - cross_size, center_y), (center_x + cross_size, center_y), 2)
            pygame.draw.line(surface, (255, 0, 0), (center_x, center_y - cross_size), (center_x, center_y + cross_size), 2)
        elif self.district == "police":
            # 경찰서는 눈에 띄는 파란 점 대신 중립적인 작은 표식으로만 표시한다.
            badge = pygame.Rect(0, 0, max(7, self.rect.width // 6), max(7, self.rect.height // 6))
            badge.center = self.rect.center
            pygame.draw.rect(surface, (70, 80, 95), badge, border_radius=2)
            pygame.draw.rect(surface, (0, 0, 0), badge, 1, border_radius=2)
        elif self.district == "park":
            # 공원 내부 요소 - 미리 생성된 나무 위치 사용
            for (tx, ty), tree_color in zip(self.park_trees, self.park_tree_colors):
                tx += ox
                ty += oy
                pygame.draw.circle(surface, tree_color, (tx, ty), 2)
                pygame.draw.circle(surface, (20, 50, 20), (tx, ty), 2, 1)  # 테두리
            # 작은 산책로
            path_color = (180, 160, 120)
            if draw_rect.width > 20 and draw_rect.height > 20:
                # 수평 산책로
                py = draw_rect.centery
                pygame.draw.line(surface, path_color, (draw_rect.left + 5, py), (draw_rect.right - 5, py), 2)
                # 수직 산책로
                px = draw_rect.centerx
                pygame.draw.line(surface, path_color, (px, draw_rect.top + 5), (px, draw_rect.bottom - 5), 2)


class EvacuationZone:
    """대피 구역. 시민이 이 안으로 들어오면 NORMAL/RESCUED 상태가 된다."""

    def __init__(self, rect: pygame.Rect):
        self.rect = rect

    def draw(self, surface, offset=(0, 0)):
        ox, oy = offset
        zone_surf = pygame.Surface(self.rect.size, pygame.SRCALPHA)
        pygame.draw.rect(zone_surf, (80, 190, 140, 120), zone_surf.get_rect(), border_radius=10)
        pygame.draw.rect(zone_surf, (0, 0, 0), zone_surf.get_rect(), 2, border_radius=10)
        surface.blit(zone_surf, (self.rect.x + ox, self.rect.y + oy))


class Helicopter:
    """구조 헬기 애니메이션."""

    def __init__(self, start_pos, target_pos, speed=260.0):
        self.pos = pygame.Vector2(start_pos)
        self.target = pygame.Vector2(target_pos)
        self.speed = speed
        self.state = "approaching"  # approaching -> hovering -> leaving
        self.hover_time = 1.4
        self.hover_timer = 0.0

    def update(self, dt: float):
        if self.state == "approaching":
            direction = self.target - self.pos
            dist = direction.length()
            if dist < 6:
                self.state = "hovering"
                self.hover_timer = 0.0
                return
            if dist > 0:
                direction = direction.normalize()
            self.pos += direction * self.speed * dt
        elif self.state == "hovering":
            self.hover_timer += dt
            if self.hover_timer >= self.hover_time:
                self.state = "leaving"
        elif self.state == "leaving":
            direction = pygame.Vector2(WIDTH + 200, -200) - self.pos
            if direction.length() > 0:
                direction = direction.normalize()
            self.pos += direction * self.speed * dt

    def is_finished(self) -> bool:
        return self.state == "leaving" and (self.pos.x > WIDTH + 150 or self.pos.y < -150)

    def draw(self, surface, offset=(0, 0)):
        ox, oy = offset
        body = pygame.Rect(0, 0, 44, 20)
        body.center = (int(self.pos.x + ox), int(self.pos.y + oy))
        pygame.draw.rect(surface, (210, 230, 240), body, border_radius=6)
        pygame.draw.rect(surface, (0, 0, 0), body, 2, border_radius=6)

        tail_start = (body.left, body.centery)
        tail_end = (body.left - 18, body.centery)
        pygame.draw.line(surface, (210, 230, 240), tail_start, tail_end, 3)

        rotor_len = 42
        t = time.time()
        ang = math.sin(t * 22.0) * 0.5
        cx, cy = body.centerx, body.top - 4
        dx = math.cos(ang) * rotor_len
        dy = math.sin(ang) * rotor_len
        pygame.draw.line(surface, (240, 240, 240), (cx - dx, cy - dy), (cx + dx, cy + dy), 3)


class PopupMessage:
    """짧게 나타나는 안내/결과 팝업 텍스트."""

    def __init__(self, text: str, color, duration: float = 2.5):
        self.text = text
        self.color = color
        self.duration = duration
        self.start_time = time.time()
        self.count = 1  # 중복된 메시지 개수

    def is_alive(self) -> bool:
        return (time.time() - self.start_time) < self.duration
    
    def add_duplicate(self):
        """중복된 메시지 개수를 늘린다."""
        self.count += 1
        self.start_time = time.time()  # 시간 초기화


###############################################################
# 메인 Game 클래스
###############################################################

class Game:
    """Disaster Commander 전체 게임 로직."""

    def __init__(self):
        pygame.init()
        pygame.mixer.init()

        self.display_flags = pygame.SCALED
        self.fullscreen = False
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), self.display_flags)
        pygame.display.set_caption("Disaster Commander")
        self.clock = pygame.time.Clock()

        # 폰트 - 더 자연스러운 한글 UI를 위해 후보군을 넓게 잡는다.
        self.font_candidates = [
            "nanumgothic",
            "notosanscjkkr",
            "notosanskr",
            "malgungothic",
            "gulim",
            "dotum",
            "applegothic",
            "dejavusans",
            "liberationsans",
        ]

        def get_safe_font(size, *, bold=False, italic=False):
            for font_name in self.font_candidates:
                try:
                    font_path = pygame.font.match_font(font_name, bold=bold, italic=italic)
                    if font_path:
                        font = pygame.font.Font(font_path, size)
                    else:
                        font = pygame.font.SysFont(font_name, size, bold=bold, italic=italic)
                    test_surface = font.render("테스트", True, (255, 255, 255))
                    if test_surface.get_width() > 0:
                        return font
                except Exception as e:
                    print(f"Warning: Failed to load font {font_name}: {e}")
                    continue
            return pygame.font.Font(None, size)

        self.font_large = get_safe_font(62, bold=True)
        self.font_medium = get_safe_font(30, bold=False)
        self.font_small = get_safe_font(20, bold=False)
        self.font_tiny = get_safe_font(15, bold=False)
        self.font_menu_title = get_safe_font(34, bold=True)
        self.font_menu_subtitle = get_safe_font(15, bold=False)
        self.font_menu_meta = get_safe_font(14, bold=False)

        # 사운드
        warn_path = create_tone("warn_tone.wav", 920, 0.25)
        rescue_path = create_tone("rescue_tone.wav", 640, 0.22)
        click_path = create_tone("click_tone.wav", 520, 0.08)
        try:
            self.sound_warning = pygame.mixer.Sound(warn_path)
        except pygame.error:
            self.sound_warning = None
        try:
            self.sound_rescue = pygame.mixer.Sound(rescue_path)
        except pygame.error:
            self.sound_rescue = None
        try:
            self.sound_click = pygame.mixer.Sound(click_path)
        except pygame.error:
            self.sound_click = None

        # 상태
        self.music_available = True
        self.audio_unlocked = False
        self.music_paused = False
        self.music_volume = 0.45
        self.current_bgm_key = None
        self.pending_bgm_key = None
        self.bgm_fade_ms = 220
        self.bgm_check_timer = 0.0
        self.bgm_check_interval = 0.5  # Check BGM state every 0.5 seconds instead of every frame
        self.bgm_switch_cooldown = 0.0
        self.bgm_switch_cooldown_time = 2.0  # Wait 2 seconds between BGM switches
        bgm_folder = os.path.join(os.path.dirname(__file__), "bgm")
        self.bgm_tracks = {
            "default": os.path.join(bgm_folder, "default_bgm.mp3"),
            "disaster": os.path.join(bgm_folder, "disaster_bgm.mp3"),
            "result": os.path.join(bgm_folder, "result_bgm.mp3"),
        }
        self.bgm_sounds = {}
        self.bgm_channel = None
        self.validate_bgm_tracks()
        self.state = STATE_MENU

        # 난이도/기록
        self.difficulty_keys = ["Easy", "Normal", "Hard"]
        self.difficulty_index = 1  # 기본: 보통
        self.difficulty_names = {"Easy": "쉬움", "Normal": "보통", "Hard": "어려움"}
        self.difficulty = self.difficulty_keys[self.difficulty_index]
        self.high_scores = self.load_high_scores()

        # 도시/점수/시간
        self.reset_game_state()

        # 버튼
        self.menu_buttons: list[Button] = []
        self.play_buttons: list[Button] = []
        self.result_buttons: list[Button] = []
        self.create_buttons()

        # 재난 정의 + 기본 확률
        self.disasters = self.create_disasters()
        # [지진, 화재, 홍수, 아무 일 없음]
        self.base_disaster_weights = [0.10, 0.20, 0.15, 0.55]

        # 필드에 존재하는 재난(여러 개 가능)
        self.active_disasters: list[DisasterInstance] = []
        self.max_active_disasters = 3

        # 애니메이션 상태
        self.shake_intensity = 0.0
        self.shake_timer = 0.0
        self.shake_duration = 1.2

        # 화면 붉은 플래시 + 중앙 경고 텍스트
        self.flash_timer = 0.0
        self.flash_duration = 0.5
        self.alert_timer = 0.0
        self.alert_duration = 1.4
        self.alert_text = ""
        self.alert_subtext = ""
        self.alert_color = (255, 255, 255)

        # 헬기
        self.helicopter: Helicopter | None = None

        # 시민 / 구조대 / 건물 / 대피 구역
        self.citizens_visual: list[Citizen] = []
        self.rescue_teams: list[RescueTeam] = []
        self.buildings: list[Building] = []
        self.evac_zones: list[EvacuationZone] = []

        # 도시 배경(절차적) + 구조물들
        self.city_surface = self.generate_city_surface()
        # 시민 아이콘은 도시 생성 후 배치
        self.generate_citizen_icons()

        # 팝업
        self.popup_messages: list[PopupMessage] = []

        # 미니맵
        self.minimap_rect = pygame.Rect(WIDTH - 210, 10, 200, 140)

        # UI 애니메이션
        self.ui_animation_progress = 0.0
        self.ui_animating = True
        self.paused = False
        self.pause_started_at = 0.0
        self.focus_index = 0
        self.game_over_finalized = False
        
        # 캐시된 메뉴 배경
        self.cached_menu_bg = None
        
        # BGM 비동기 로딩을 위한 스레드 변수
        self.bgm_loading_thread = None
        self.bgm_to_load = None

    ###########################################################
    # 초기화 / 버튼 / 재난 정의
    ###########################################################

    def reset_game_state(self):
        """도시 및 점수, 시간, 재난 상태를 초기화."""
        self.citizens = 300
        self.initial_citizens = self.citizens
        self.hospital_capacity = 100

        # 명령 포인트/쿨다운 초기값 (apply_difficulty_settings가 참조함)
        self.command_points = 0
        self.max_command_points = 0
        self.command_regen_rate = 0.0

        # 난이도 기반 밸런스 세팅
        self.apply_difficulty_settings()
        self.command_points = self.max_command_points

        # pygame dt 기반 시간 추적
        self.accumulated_time = 0.0
        self.pause_accumulated_time = 0.0
        self.last_elapsed_time = 0.0
        self.start_time = time.time()  # Temporary fallback

        self.score = 0
        self.total_deaths = 0
        self.total_rescues = 0
        self.events_handled = 0
        self.rescued_citizens = 0
        self.coins = 0
        self.total_coins_earned = 0
        self.remaining_citizens = self.citizens
        self.focus_index = 0
        self.game_over_finalized = False
        self.paused = False
        self.pause_started_at = 0.0
        self.combo_count = 0
        self.combo_timer = 0.0
        self.combo_window = 8.0
        self.last_action_summary = "대응 준비 완료"
        self.last_end_reason = ""
        self.start_briefing_timer = 3.0
        self.tutorial_hint_timer = 15.0
        self.evac_mode_active = False
        self.evac_player_citizen = None
        self.evac_mode_successes = 0
        self.ui_hidden = False
        self.popup_queue = []
        self.camera_offset = pygame.Vector2(0, 0)
        self.map_dragging = False
        self.map_drag_last = None
        self.difficulty_objectives = {
            "Easy": {"rescues": 180, "deaths": 90},
            "Normal": {"rescues": 260, "deaths": 110},
            "Hard": {"rescues": 280, "deaths": 95},
        }

        self.active_disasters = []
        self.disaster_decision_time_limit = 10.0
        self.next_event_game_time = 3.0

        self.helicopter = None
        self.shake_intensity = 0.0
        self.shake_timer = 0.0
        self.flash_timer = 0.0
        self.alert_timer = 0.0
        self.alert_text = ""
        self.alert_subtext = ""
        self.popup_messages = []

        # UI 애니메이션 리셋
        self.ui_animation_progress = 0.0
        self.ui_animating = True

        # 연쇄 재난 시스템
        self.chain_disaster_chance = 0.3  # 지진 후 연쇄 재난 확률
        self.last_chain_time = 0.0
        self.chain_cooldown_time = 8.0  # 연쇄 재난 간 최소 간격
        
        # 자원 관리 시스템
        self.budget = 1500  # 초기 예산
        self.max_budget = 3000
        self.manpower = 50  # 가용 인력
        self.max_manpower = 100
        self.materials = 200  # 물자
        self.max_materials = 400
        
        # 자원 재생률 (초당)
        self.budget_regen_rate = 1.2
        self.manpower_regen_rate = 1.0
        self.materials_regen_rate = 0.3

        # 상점 시스템
        self.shop_open = False
        self.shop_paused_by_us = False
        self.shop_upgrades = {
            "manpower": {
                "name": "인력 충원",
                "cost": 12,
                "cost_growth": 6,
                "max_level": 8,
                "desc": "최대 인력 +10, 현재 인력 +6, 재생 +0.15",
            },
            "budget": {
                "name": "예산 지원",
                "cost": 10,
                "cost_growth": 5,
                "max_level": 8,
                "desc": "최대 예산 +200, 현재 예산 +120",
            },
            "materials": {
                "name": "물자 확보",
                "cost": 10,
                "cost_growth": 5,
                "max_level": 8,
                "desc": "최대 물자 +100, 현재 물자 +60",
            },
            "command": {
                "name": "지휘 보강",
                "cost": 14,
                "cost_growth": 7,
                "max_level": 5,
                "desc": "최대 명령 포인트 +1, 즉시 전량 회복",
            },
        }
        self.shop_levels = {key: 0 for key in self.shop_upgrades}

        # 명령 포인트 / 쿨다운
        self.command_points = self.max_command_points
        self.command_timers = {
            "대피령": 0.0,
            "구조대 파견": 0.0,
            "소방대 투입": 0.0,
            "의료 지원": 0.0,
            "헬기 구조": 0.0,
            "경찰 통제": 0.0,
            "관찰 모드": 0.0,
        }
        self.command_costs = {
            "대피령": 1,
            "구조대 파견": 2,
            "소방대 투입": 3,
            "의료 지원": 2,
            "헬기 구조": 4,
            "경찰 통제": 2,
            "관찰 모드": 0,
        }
        self.command_cooldowns = {
            "대피령": 5.0,
            "구조대 파견": 8.0,
            "소방대 투입": 12.0,
            "의료 지원": 10.0,
            "헬기 구조": 18.0,
            "경찰 통제": 12.0,
            "관찰 모드": 3.0,
        }

        # 눈 파티클
        self.snow_particles = []
        self.init_snow_particles()
        # 구조대 초기 위치는 대피 구역이 생성된 후 갱신된다.
        self.rescue_teams = []
        self.buildings = []
        self.evac_zones = []
        self.river_zones = []
        self.bridge_zones = []

        # 선택된 구역
        self.selected_district = None

        if hasattr(self, "screen"):
            self.city_surface = self.generate_city_surface()
            self.generate_citizen_icons()

    def create_icon_circle(self, color) -> pygame.Surface:
        surf = pygame.Surface((28, 28), pygame.SRCALPHA)
        pygame.draw.circle(surf, color, (14, 14), 11)
        pygame.draw.circle(surf, (0, 0, 0), (14, 14), 11, 2)
        return surf

    def create_icon_triangle(self, color) -> pygame.Surface:
        surf = pygame.Surface((28, 28), pygame.SRCALPHA)
        pts = [(4, 22), (24, 22), (14, 6)]
        pygame.draw.polygon(surf, color, pts)
        pygame.draw.polygon(surf, (0, 0, 0), pts, 2)
        return surf

    def create_icon_cross(self, color) -> pygame.Surface:
        surf = pygame.Surface((28, 28), pygame.SRCALPHA)
        pygame.draw.circle(surf, (20, 20, 20), (14, 14), 11)
        pygame.draw.line(surf, color, (8, 8), (20, 20), 3)
        pygame.draw.line(surf, color, (20, 8), (8, 20), 3)
        pygame.draw.circle(surf, (0, 0, 0), (14, 14), 11, 2)
        return surf

    def create_buttons(self):
        """시작/플레이/결과 화면 버튼 설정."""
        # 메뉴
        start_rect = (WIDTH // 2 - 130, HEIGHT // 2 + 205, 260, 62)
        play_icon = self.create_icon_triangle((255, 255, 255))
        start_btn = Button(
            start_rect,
            "게임 시작",
            self.font_medium,
            (60, 130, 210),
            (90, 160, 240),
            icon_surface=play_icon,
        )
        self.menu_buttons = [start_btn]

        # 전체화면 버튼
        fullscreen_btn = Button(
            (WIDTH // 2 + 180, HEIGHT // 2 + 60, 120, 40),
            "전체화면",
            self.font_small,
            (80, 80, 120),
            (100, 100, 140),
            text_color=(240, 240, 240),
        )
        self.fullscreen_button = fullscreen_btn
        self.menu_buttons.append(fullscreen_btn)

        # 난이도 선택 버튼
        # 메뉴 난이도 선택 버튼 위치 조정 (아래로 내리기)
        self.diff_left_button = Button(
            (WIDTH // 2 - 175, HEIGHT // 2 + 132, 46, 46),
            "<",
            self.font_medium,
            (110, 110, 110),
            (150, 150, 150),
            text_color=(240, 240, 240),
        )
        self.diff_right_button = Button(
            (WIDTH // 2 + 129, HEIGHT // 2 + 132, 46, 46),
            ">",
            self.font_medium,
            (110, 110, 110),
            (150, 150, 150),
            text_color=(240, 240, 240),
        )

        # 플레이 액션 버튼
        button_width = 130
        button_height = 44
        gap = 10
        start_x = 20
        y = HEIGHT - 100

        evac_icon = self.create_icon_triangle((230, 230, 255))
        rescue_icon = self.create_icon_circle((230, 255, 230))
        watch_icon = self.create_icon_circle((255, 230, 230))
        fire_icon = self.create_icon_triangle((255, 100, 0))
        medical_icon = self.create_icon_circle((255, 255, 255))
        heli_icon = self.create_icon_triangle((0, 255, 0))
        police_icon = self.create_icon_circle((0, 0, 255))

        # 버튼 텍스트가 길기 때문에 기본 폰트를 더 작게 사용
        cmd_font = self.font_tiny

        self.button_evac = Button(
            (start_x, y, button_width, button_height),
            "대피령",
            cmd_font,
            (90, 90, 210),
            (120, 120, 240),
            icon_surface=evac_icon,
            command_key="대피령",
            tooltip="포인트 1 / 쿨다운 5초",
        )
        self.button_rescue = Button(
            (start_x + (button_width + gap), y, button_width, button_height),
            "구조대 파견",
            cmd_font,
            (70, 170, 100),
            (100, 200, 130),
            icon_surface=rescue_icon,
            command_key="구조대 파견",
            tooltip="포인트 2 / 쿨다운 8초",
        )
        self.button_fire = Button(
            (start_x + 2 * (button_width + gap), y, button_width, button_height),
            "소방대 투입",
            cmd_font,
            (210, 70, 70),
            (240, 100, 100),
            icon_surface=fire_icon,
            command_key="소방대 투입",
            tooltip="포인트 3 / 쿨다운 12초",
        )
        self.button_medical = Button(
            (start_x + 3 * (button_width + gap), y, button_width, button_height),
            "의료 지원",
            cmd_font,
            (255, 255, 255),
            (200, 200, 200),
            icon_surface=medical_icon,
            command_key="의료 지원",
            tooltip="포인트 2 / 쿨다운 10초",
        )
        self.button_heli = Button(
            (start_x + 4 * (button_width + gap), y, button_width, button_height),
            "헬기 구조",
            cmd_font,
            (70, 210, 70),
            (100, 240, 100),
            icon_surface=heli_icon,
            command_key="헬기 구조",
            tooltip="포인트 4 / 쿨다운 18초",
        )
        self.button_police = Button(
            (start_x + 5 * (button_width + gap), y, button_width, button_height),
            "경찰 통제",
            cmd_font,
            (70, 70, 210),
            (100, 100, 240),
            icon_surface=police_icon,
            command_key="경찰 통제",
            tooltip="포인트 2 / 쿨다운 12초",
        )
        self.button_watch = Button(
            (start_x + 6 * (button_width + gap), y, button_width, button_height),
            "관찰 모드",
            cmd_font,
            (170, 80, 80),
            (200, 110, 110),
            icon_surface=watch_icon,
            command_key="관찰 모드",
            tooltip="포인트 0 / 쿨다운 3초",
        )
        shop_icon = self.create_icon_circle((255, 210, 80))
        self.button_shop = Button(
            (start_x + 7 * (button_width + gap), y, button_width, button_height),
            "상점",
            cmd_font,
            (140, 110, 60),
            (180, 145, 80),
            icon_surface=shop_icon,
            command_key="SHOP",
            tooltip="코인으로 인력/자원 업그레이드",
        )
        ui_toggle_font = self.font_tiny
        self.button_ui_toggle = Button(
            (WIDTH - 96, HEIGHT - 44, 84, 30),
            "UI 숨김",
            ui_toggle_font,
            (45, 70, 110),
            (70, 105, 150),
            text_color=(240, 245, 255),
            command_key="UI_TOGGLE",
            tooltip="HUD 표시/숨김",
        )
        self.play_buttons = [
            self.button_evac,
            self.button_rescue,
            self.button_fire,
            self.button_medical,
            self.button_heli,
            self.button_police,
            self.button_watch,
            self.button_shop,
        ]
        self.action_shortcuts = {
            pygame.K_1: self.button_evac.command_key,
            pygame.K_2: self.button_rescue.command_key,
            pygame.K_3: self.button_fire.command_key,
            pygame.K_4: self.button_medical.command_key,
            pygame.K_5: self.button_heli.command_key,
            pygame.K_6: self.button_police.command_key,
            pygame.K_7: self.button_watch.command_key,
        }

        manpower_icon = self.create_icon_circle((120, 220, 140))
        budget_icon = self.create_icon_circle((255, 215, 100))
        materials_icon = self.create_icon_circle((255, 155, 100))
        command_icon = self.create_icon_triangle((140, 220, 255))
        close_icon = self.create_icon_cross((255, 220, 220))
        self.shop_buttons = [
            Button((0, 0, 1, 1), "인력 충원", self.font_small, (70, 150, 90), (95, 180, 110), icon_surface=manpower_icon, command_key="SHOP_MANPOWER"),
            Button((0, 0, 1, 1), "예산 지원", self.font_small, (150, 125, 60), (180, 150, 80), icon_surface=budget_icon, command_key="SHOP_BUDGET"),
            Button((0, 0, 1, 1), "물자 확보", self.font_small, (150, 95, 55), (180, 120, 75), icon_surface=materials_icon, command_key="SHOP_MATERIALS"),
            Button((0, 0, 1, 1), "지휘 보강", self.font_small, (70, 110, 160), (95, 140, 190), icon_surface=command_icon, command_key="SHOP_COMMAND"),
            Button((0, 0, 1, 1), "닫기", self.font_small, (130, 70, 70), (170, 95, 95), icon_surface=close_icon, command_key="SHOP_CLOSE"),
        ]

        # 결과 화면 버튼
        retry_rect = (WIDTH // 2 - 180, HEIGHT // 2 + 140, 160, 55)
        quit_rect = (WIDTH // 2 + 20, HEIGHT // 2 + 140, 160, 55)
        retry_icon = self.create_icon_circle((230, 240, 255))
        quit_icon = self.create_icon_cross((255, 240, 240))

        retry_btn = Button(
            retry_rect,
            "다시 하기",
            self.font_medium,
            (70, 130, 210),
            (100, 160, 240),
            icon_surface=retry_icon,
        )
        quit_btn = Button(
            quit_rect,
            "종료",
            self.font_medium,
            (170, 80, 80),
            (200, 110, 110),
            icon_surface=quit_icon,
        )
        self.result_buttons = [retry_btn, quit_btn]

    def create_disasters(self) -> list[Disaster]:
        """각 재난 타입 정의."""
        disasters = []

        eq_actions = {
            "대피령": {"death_range": (5, 30), "rescue_range": (10, 40)},
            "구조대 파견": {"death_range": (10, 40), "rescue_range": (20, 60)},
            "소방대 투입": {"death_range": (15, 50), "rescue_range": (5, 20)},
            "의료 지원": {"death_range": (5, 20), "rescue_range": (30, 70)},
            "헬기 구조": {"death_range": (5, 15), "rescue_range": (40, 80)},
            "경찰 통제": {"death_range": (10, 30), "rescue_range": (15, 45)},
            "관찰 모드": {"death_range": (30, 80), "rescue_range": (0, 10)},
            "no_action": {"death_range": (40, 100), "rescue_range": (0, 5)},
        }
        disasters.append(
            Disaster(
                "지진",
                "EARTHQUAKE!",
                "도시 전역에 강한 지진이 발생했습니다!",
                (230, 100, 100),
                0.9,
                eq_actions,
                "earthquake",
            )
        )

        flood_actions = {
            "대피령": {"death_range": (5, 20), "rescue_range": (10, 30)},
            "구조대 파견": {"death_range": (8, 25), "rescue_range": (15, 45)},
            "소방대 투입": {"death_range": (10, 30), "rescue_range": (5, 15)},
            "의료 지원": {"death_range": (5, 15), "rescue_range": (20, 50)},
            "헬기 구조": {"death_range": (3, 10), "rescue_range": (35, 70)},
            "경찰 통제": {"death_range": (5, 15), "rescue_range": (25, 55)},
            "관찰 모드": {"death_range": (15, 40), "rescue_range": (0, 10)},
            "no_action": {"death_range": (30, 70), "rescue_range": (0, 10)},
        }
        disasters.append(
            Disaster(
                "홍수",
                "FLOOD!",
                "집중 호우로 인해 하천이 범람하고 있습니다!",
                (90, 150, 240),
                0.8,
                flood_actions,
                "flood",
            )
        )

        blizzard_actions = {
            "대피령": {"death_range": (2, 10), "rescue_range": (5, 20)},
            "구조대 파견": {"death_range": (2, 15), "rescue_range": (10, 30)},
            "소방대 투입": {"death_range": (5, 20), "rescue_range": (2, 10)},
            "의료 지원": {"death_range": (1, 5), "rescue_range": (25, 50)},
            "헬기 구조": {"death_range": (10, 30), "rescue_range": (5, 20)},
            "경찰 통제": {"death_range": (3, 10), "rescue_range": (15, 35)},
            "관찰 모드": {"death_range": (8, 25), "rescue_range": (0, 8)},
            "no_action": {"death_range": (15, 40), "rescue_range": (0, 5)},
        }
        disasters.append(
            Disaster(
                "폭설",
                "BLIZZARD!",
                "도시 전역에 기록적인 폭설이 내리고 있습니다!",
                (220, 220, 255),
                0.6,
                blizzard_actions,
                "blizzard",
            )
        )

        wildfire_actions = {
            "대피령": {"death_range": (3, 20), "rescue_range": (5, 25)},
            "구조대 파견": {"death_range": (5, 25), "rescue_range": (15, 50)},
            "소방대 투입": {"death_range": (2, 10), "rescue_range": (40, 80)},
            "의료 지원": {"death_range": (5, 15), "rescue_range": (20, 50)},
            "헬기 구조": {"death_range": (2, 8), "rescue_range": (45, 90)},
            "경찰 통제": {"death_range": (8, 25), "rescue_range": (10, 30)},
            "관찰 모드": {"death_range": (15, 50), "rescue_range": (0, 10)},
            "no_action": {"death_range": (30, 80), "rescue_range": (0, 10)},
        }
        disasters.append(
            Disaster(
                "화재",
                "FIRE!",
                "도심 지역에서 화재가 발생했습니다!",
                (255, 150, 70),
                0.7,
                wildfire_actions,
                "wildfire",
            )
        )

        none_actions = {
            "대피령": {"death_range": (0, 0), "rescue_range": (0, 0)},
            "구조대 파견": {"death_range": (0, 0), "rescue_range": (0, 0)},
            "소방대 투입": {"death_range": (0, 0), "rescue_range": (0, 0)},
            "의료 지원": {"death_range": (0, 0), "rescue_range": (0, 0)},
            "헬기 구조": {"death_range": (0, 0), "rescue_range": (0, 0)},
            "경찰 통제": {"death_range": (0, 0), "rescue_range": (0, 0)},
            "관찰 모드": {"death_range": (0, 0), "rescue_range": (0, 0)},
            "no_action": {"death_range": (0, 0), "rescue_range": (0, 0)},
        }
        disasters.append(
            Disaster(
                "아무 일 없음",
                "",
                "오늘은 유난히 조용합니다.",
                (130, 130, 130),
                0.0,
                none_actions,
                "none",
            )
        )

        return disasters

    ###########################################################
    # 도시/시민/배경 생성
    ###########################################################

    def generate_citizen_icons(self):
        """도로와 강을 피해 시민 아이콘 배치."""
        self.citizens_visual = []
        rnd = random.Random(42)
        
        # Pre-calculate valid positions to avoid repeated checks
        valid_positions = []
        for x in range(40, WIDTH - 260, 8):  # Step by 8 to reduce checks
            for y in range(100, HEIGHT - 140, 8):
                if y < 80 or y > HEIGHT - 140:
                    continue
                if not self.is_position_blocked(pygame.Vector2(x, y)):
                    valid_positions.append((x, y))
        
        # Randomly select from valid positions
        if valid_positions:
            num_citizens = min(300, len(valid_positions))
            selected_positions = rnd.sample(valid_positions, num_citizens)
            for x, y in selected_positions:
                self.citizens_visual.append(Citizen(x, y))

    def generate_city_surface(self) -> pygame.Surface:
        """
        도시 블록 구조 기반의 절차적 도시 생성.
        1) 격자형 도로 네트워크
        2) 도로 사이 블록을 계산
        3) 블록 내부에 정렬된 건물/공원/병원/대피소 배치
        4) 직선형 강 + 다리
        """
        surf = pygame.Surface((WIDTH, HEIGHT))
        surf.fill((32, 54, 80))

        rnd = random.Random()

        self.buildings = []
        self.evac_zones = []
        self.river_zones = []

        # 1. 도로 네트워크
        road_color = (60, 60, 72)
        h_margin, v_margin = 60, 90
        x_spacing = rnd.randint(120, 160)
        y_spacing = rnd.randint(120, 160)
        vertical_roads = []
        x = h_margin
        while x < WIDTH - 260:
            vertical_roads.append(x)
            x += x_spacing
        horizontal_roads = []
        y = v_margin
        while y < HEIGHT - 160:
            horizontal_roads.append(y)
            y += y_spacing

        road_w = 34
        road_h = 30
        for rx in vertical_roads:
            pygame.draw.rect(surf, road_color, (rx, 0, road_w, HEIGHT))
        for ry in horizontal_roads:
            pygame.draw.rect(surf, road_color, (0, ry, WIDTH, road_h))

        # 도로 차선
        lane_color = (120, 120, 130)
        for rx in vertical_roads:
            for yy in range(0, HEIGHT, 24):
                pygame.draw.rect(surf, lane_color, (rx + road_w // 2 - 2, yy, 4, 10))
        for ry in horizontal_roads:
            for xx in range(0, WIDTH - 260, 26):
                pygame.draw.rect(surf, lane_color, (xx, ry + road_h // 2 - 2, 12, 4))

        # 2. 강 생성 (직선)
        river_color = (70, 110, 170)
        river_outline_color = (50, 80, 130)
        river_y = rnd.randint(int(HEIGHT * 0.33), int(HEIGHT * 0.38))
        river_top = river_y - 34
        river_bottom = river_y + 34
        river_rect = pygame.Rect(-40, river_top, WIDTH - 220, river_bottom - river_top)

        # 강 영역(충돌/건물 배치 방지용)
        self.river_zones = []
        self.bridge_zones = []
        self.river_zones.append(river_rect)

        # 다리: 세로 도로가 강과 만나는 실제 교차 지점에만 생성
        bridge_color = (90, 90, 95)
        bridge_guard = (170, 170, 185)
        self.bridge_zones = []
        # 3. 도시 블록(도로 사이 영역) 순회
        def road_bounds_x():
            xs = [h_margin - road_w] + vertical_roads + [WIDTH - 260 + road_w]
            xs.sort()
            return xs

        def road_bounds_y():
            ys = [v_margin - road_h] + horizontal_roads + [HEIGHT - 140 + road_h]
            ys.sort()
            return ys

        xs = road_bounds_x()
        ys = road_bounds_y()

        for ix in range(len(xs) - 1):
            for iy in range(len(ys) - 1):
                left = xs[ix] + road_w
                right = xs[ix + 1]
                top = ys[iy] + road_h
                bottom = ys[iy + 1]
                block_rect = pygame.Rect(
                    left + 6,
                    top + 6,
                    max(0, right - left - 12),
                    max(0, bottom - top - 12),
                )
                if block_rect.width < 40 or block_rect.height < 40:
                    continue

                # 블록 타입 결정
                r = rnd.random()
                if r < 0.08:
                    block_type = "park"
                elif r < 0.11:
                    block_type = "hospital"
                elif r < 0.14:
                    block_type = "police"
                elif r < 0.55:
                    block_type = "residential"
                else:
                    block_type = "industrial"

                # 강이 지나는 블록은 건물 배치하지 않음
                if any(block_rect.colliderect(r) for r in self.river_zones):
                    continue

                # 4. 블록 내부에 정렬된 건물/공원/병원/대피소 배치
                cols = max(1, int(block_rect.width // rnd.uniform(30, 50)))
                rows = max(1, int(block_rect.height // rnd.uniform(30, 50)))
                cell_w = block_rect.width / cols
                cell_h = block_rect.height / rows

                for cx in range(cols):
                    for cy in range(rows):
                        cx0 = block_rect.x + cx * cell_w + 4 + rnd.uniform(-cell_w*0.1, cell_w*0.1)
                        cy0 = block_rect.y + cy * cell_h + 4 + rnd.uniform(-cell_h*0.1, cell_h*0.1)
                        cw = cell_w - 8
                        ch = cell_h - 8
                        if cw < 16 or ch < 16:
                            continue

                        b_rect = pygame.Rect(
                            int(cx0),
                            int(cy0),
                            int(cw * rnd.uniform(0.6, 1.0)),
                            int(ch * rnd.uniform(0.6, 1.0)),
                        )

                        building = Building(b_rect, block_type)
                        self.buildings.append(building)

        # 강을 먼저 그리고, 세로 다리를 교차 지점에만 덮어 씀
        pygame.draw.rect(surf, river_color, river_rect)
        pygame.draw.rect(surf, river_outline_color, river_rect, 6)
        for rx in vertical_roads:
            road_center_x = rx + road_w // 2
            if not (river_rect.left + 24 <= road_center_x <= river_rect.right - 24):
                continue
            bridge_rect = pygame.Rect(0, 0, 22, river_rect.height + 18)
            bridge_rect.center = (road_center_x, river_rect.centery)
            self.bridge_zones.append(bridge_rect.inflate(14, 8))
            pygame.draw.rect(surf, bridge_color, bridge_rect, border_radius=4)
            pygame.draw.rect(surf, bridge_guard, bridge_rect, 2, border_radius=4)
            pygame.draw.line(surf, (210, 210, 220), (bridge_rect.centerx, bridge_rect.top + 8), (bridge_rect.centerx, bridge_rect.bottom - 8), 2)

        # 주요 공공건물을 대피 구역으로 변환
        candidates = [
            b for b in self.buildings
            if b.district in ("hospital", "police") and not b.collapsed
        ]
        candidates.sort(key=lambda b: (0 if b.district == "hospital" else 1, -b.rect.width * b.rect.height))
        self.evac_zones = []
        for building in candidates:
            zone_rect = building.rect.inflate(26, 26)
            zone_rect.x = max(24, min(WIDTH - 280 - zone_rect.width, zone_rect.x))
            zone_rect.y = max(84, min(HEIGHT - 150 - zone_rect.height, zone_rect.y))
            if any(zone.rect.colliderect(zone_rect.inflate(20, 20)) for zone in self.evac_zones):
                continue
            self.evac_zones.append(EvacuationZone(zone_rect))
            if len(self.evac_zones) >= 3:
                break

        if not self.evac_zones:
            fallback_rects = [
                pygame.Rect(90, HEIGHT - 220, 96, 70),
                pygame.Rect(WIDTH - 420, 120, 96, 70),
            ]
            for rect in fallback_rects:
                self.evac_zones.append(EvacuationZone(rect))

        # 초기 구조대 스폰: 첫 번째 대피 구역이 있으면 그 근처에 생성
        self.rescue_teams = []
        if self.evac_zones:
            base = self.evac_zones[0].rect.center
            for i in range(3):
                off_x = -28 + i * 28
                self.rescue_teams.append(RescueTeam(base[0] + off_x, base[1] + 14))

        return surf

    ###########################################################
    # 사운드/점수/난이도 유틸
    ###########################################################

    def play_warning_sound(self):
        if self.sound_warning:
            try:
                self.sound_warning.play()
            except Exception as e:
                print(f"Warning: Failed to play warning sound: {e}")

    def play_rescue_sound(self):
        if self.sound_rescue:
            try:
                self.sound_rescue.play()
            except Exception as e:
                print(f"Warning: Failed to play rescue sound: {e}")

    def play_click_sound(self):
        if self.sound_click:
            try:
                self.sound_click.play()
            except Exception as e:
                print(f"Warning: Failed to play click sound: {e}")

    def validate_bgm_tracks(self):
        """실제 파일이 없는 경우 음악 시스템을 안전하게 비활성화한다."""
        missing = [path for path in self.bgm_tracks.values() if not os.path.exists(path)]
        if missing:
            self.music_available = False
            self.bgm_sounds = {}
            self.bgm_channel = None
            return

        try:
            self.bgm_sounds = {
                key: pygame.mixer.Sound(path)
                for key, path in self.bgm_tracks.items()
            }
            pygame.mixer.set_reserved(1)
            self.bgm_channel = pygame.mixer.Channel(0)
        except pygame.error:
            self.music_available = False
            self.bgm_sounds = {}
            self.bgm_channel = None

    def unlock_audio(self):
        """
        사용자 입력 이후에만 BGM을 시작한다.
        브라우저 자동재생 제한과 비슷한 정책을 의식한 안전장치다.
        """
        if not self.music_available or self.audio_unlocked:
            return
        self.audio_unlocked = True
        if self.pending_bgm_key:
            self.play_bgm(self.pending_bgm_key)

    def set_bgm_volume(self, volume: float):
        """BGM 볼륨을 0.0 ~ 1.0 범위에서 조정한다."""
        self.music_volume = max(0.0, min(1.0, volume))
        if self.music_available and self.bgm_channel is not None:
            self.bgm_channel.set_volume(self.music_volume)

    def play_bgm(self, bgm_key: str, fade_ms: int | None = None, restart: bool = False):
        """Request a BGM track and start it if audio is unlocked."""
        if not self.music_available or bgm_key not in self.bgm_sounds:
            return
        self.pending_bgm_key = bgm_key
        if not self.audio_unlocked:
            return
        if bgm_key == self.current_bgm_key and self.bgm_channel is not None and self.bgm_channel.get_busy() and not restart:
            return
        self.switch_bgm(bgm_key, fade_ms)

    def switch_bgm(self, bgm_key: str, fade_ms: int | None = None):
        """Fade out the current track and play the requested one in a loop."""
        if not self.music_available or bgm_key not in self.bgm_sounds:
            return
        self.pending_bgm_key = bgm_key
        if not self.audio_unlocked:
            return
        try:
            fade = fade_ms if fade_ms is not None else self.bgm_fade_ms
            if self.bgm_channel is None:
                pygame.mixer.set_reserved(1)
                self.bgm_channel = pygame.mixer.Channel(0)
            if self.bgm_channel.get_busy():
                self.bgm_channel.fadeout(fade)
            self.bgm_channel.set_volume(self.music_volume)
            self.bgm_channel.play(self.bgm_sounds[bgm_key], loops=-1, fade_ms=fade)
            self.current_bgm_key = bgm_key
            self.music_paused = False
        except pygame.error:
            self.music_available = False

    def pause_bgm(self):
        """Pause currently playing BGM."""
        if self.music_available and self.bgm_channel is not None and self.bgm_channel.get_busy() and not self.music_paused:
            self.bgm_channel.pause()
            self.music_paused = True

    def resume_bgm(self):
        """Resume paused BGM."""
        if self.music_available and self.music_paused:
            if self.bgm_channel is not None:
                self.bgm_channel.unpause()
            self.music_paused = False

    def update_bgm_state(self, dt: float = 0.0):
        """Keep the BGM aligned with the current game state."""
        unresolved = any(not inst.resolved for inst in self.active_disasters)
        if self.state == STATE_GAME_OVER:
            desired = "result"
        elif self.state == STATE_PLAYING and unresolved:
            desired = "disaster"
        else:
            desired = "default"

        if desired != self.current_bgm_key or (self.audio_unlocked and (self.bgm_channel is None or not self.bgm_channel.get_busy())):
            self.switch_bgm(desired)

    def get_high_score_path(self) -> str:
        return os.path.join(os.path.dirname(__file__), "high_scores.json")

    def load_high_scores(self) -> dict:
        path = self.get_high_score_path()
        default = {k: 0 for k in self.difficulty_keys}
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for k in default:
                            if k in data and isinstance(data[k], (int, float)):
                                default[k] = int(data[k])
        except Exception:
            pass
        return default

    def save_high_scores(self):
        try:
            with open(self.get_high_score_path(), "w", encoding="utf-8") as f:
                json.dump(self.high_scores, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def apply_difficulty_settings(self):
        """난이도에 따라 게임 밸런스를 조정."""
        if self.difficulty == "Easy":
            self.total_time_limit = 6 * 60 + 30  # 6분 30초 - 초보자를 위한 넉넉한 시간
            self.command_regen_rate = 1.2
            self.max_command_points = 6
            self.base_disaster_weights = [0.08, 0.16, 0.12, 0.64]
            self.max_active_disasters = 2
            self.difficulty_multiplier = 0.75
        elif self.difficulty == "Hard":
            self.total_time_limit = 2 * 60  # 2분 - 너무 빡세지 않게 완화
            self.command_regen_rate = 0.9
            self.max_command_points = 4
            self.base_disaster_weights = [0.14, 0.22, 0.16, 0.48]
            self.max_active_disasters = 2
            self.difficulty_multiplier = 0.95
        else:  # Normal
            self.total_time_limit = 3 * 60 + 30  # 3분 30초 - 표준 시간
            self.command_regen_rate = 0.8
            self.max_command_points = 5
            self.base_disaster_weights = [0.10, 0.20, 0.15, 0.55]
            self.max_active_disasters = 3
            self.difficulty_multiplier = 1.0

        # 즉시 반영(게임 중일 때도 가능)
        self.command_points = min(self.command_points, self.max_command_points)

    def change_difficulty(self, delta: int):
        self.difficulty_index = (self.difficulty_index + delta) % len(self.difficulty_keys)
        self.difficulty = self.difficulty_keys[self.difficulty_index]
        self.apply_difficulty_settings()

    def calculate_final_score(self) -> int:
        """최종 점수(0 미만 불가)."""
        return max(0, int(self.score))

    def grade_from_score(self, score: int) -> str:
        if score >= 18000:
            return "S"
        if score >= 13000:
            return "A"
        if score >= 8000:
            return "B"
        return "C"

    def finalize_game_over(self):
        """게임 종료 시점에 점수/기록 처리를 수행."""
        final_score = self.calculate_final_score()
        # 누적 플레이 시간은 일시정지 시간을 제외한 값으로 고정한다.
        self.last_elapsed_time = min(self.total_time_limit, self.accumulated_time)
        hs = self.high_scores.get(self.difficulty, 0)
        self.last_final_score = final_score
        self.last_grade = self.grade_from_score(final_score)
        self.last_record = False
        if final_score > hs:
            self.high_scores[self.difficulty] = final_score
            self.save_high_scores()
            self.last_record = True

    def end_run(self, reason: str = ""):
        if self.game_over_finalized:
            return
        self.paused = False
        self.shop_open = False
        self.shop_paused_by_us = False
        self.last_end_reason = reason
        self.game_over_finalized = True
        self.finalize_game_over()
        self.state = STATE_GAME_OVER

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        flags = self.display_flags | (pygame.FULLSCREEN if self.fullscreen else 0)
        try:
            self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags)
        except pygame.error:
            fallback_flags = pygame.FULLSCREEN if self.fullscreen else 0
            try:
                self.screen = pygame.display.set_mode((WIDTH, HEIGHT), fallback_flags)
            except pygame.error:
                self.fullscreen = not self.fullscreen
                self.screen = pygame.display.set_mode((WIDTH, HEIGHT), self.display_flags)

    def toggle_pause(self):
        if self.state != STATE_PLAYING:
            return

        now = time.time()
        if not self.paused:
            self.paused = True
            self.pause_started_at = now
            self.pause_bgm()
            return

        paused_duration = now - self.pause_started_at
        self.paused = False
        self.resume_bgm()
        self.start_time += paused_duration
        for inst in self.active_disasters:
            inst.start_time += paused_duration
            inst.decision_start_time += paused_duration
        for popup in self.popup_messages:
            popup.start_time += paused_duration

    def toggle_shop(self):
        if self.state != STATE_PLAYING:
            return

        if not self.shop_open:
            self.shop_open = True
            self.shop_paused_by_us = False
            if not self.paused:
                self.toggle_pause()
                self.shop_paused_by_us = True
            self.add_popup("상점이 열렸습니다.", (255, 220, 120), 1.2)
            return

        self.close_shop()

    def close_shop(self):
        """상점을 닫는다. 게임 종료와는 무관하다."""
        if not self.shop_open:
            return

        self.shop_open = False
        if self.shop_paused_by_us and self.paused:
            self.toggle_pause()
        self.shop_paused_by_us = False

    def toggle_ui_hidden(self):
        if self.state != STATE_PLAYING:
            return
        self.ui_hidden = not self.ui_hidden
        if self.ui_hidden:
            self.add_popup("UI 숨김", (160, 210, 255), 1.0)
        else:
            self.add_popup("UI 표시", (160, 210, 255), 1.0)

    def clamp_camera_offset(self):
        self.camera_offset.x = max(-110, min(110, self.camera_offset.x))
        self.camera_offset.y = max(-70, min(70, self.camera_offset.y))

    def get_shop_upgrade_cost(self, upgrade_key: str) -> int:
        upgrade = self.shop_upgrades.get(upgrade_key)
        if not upgrade:
            return 0
        level = self.shop_levels.get(upgrade_key, 0)
        return upgrade["cost"] + level * upgrade["cost_growth"]

    def can_buy_shop_upgrade(self, upgrade_key: str) -> bool:
        upgrade = self.shop_upgrades.get(upgrade_key)
        if not upgrade:
            return False
        level = self.shop_levels.get(upgrade_key, 0)
        if level >= upgrade["max_level"]:
            return False
        return self.coins >= self.get_shop_upgrade_cost(upgrade_key)

    def buy_shop_upgrade(self, upgrade_key: str):
        upgrade = self.shop_upgrades.get(upgrade_key)
        if not upgrade:
            return

        level = self.shop_levels.get(upgrade_key, 0)
        if level >= upgrade["max_level"]:
            self.add_popup("이미 최대 레벨입니다.", (180, 220, 255), 1.6)
            return

        cost = self.get_shop_upgrade_cost(upgrade_key)
        if self.coins < cost:
            self.add_popup("코인이 부족합니다.", (255, 140, 140), 1.6)
            return

        self.coins -= cost
        self.shop_levels[upgrade_key] = level + 1

        if upgrade_key == "manpower":
            self.max_manpower += 10
            self.manpower = min(self.max_manpower, self.manpower + 6)
            self.manpower_regen_rate += 0.25
            msg = f"인력 충원 Lv.{level + 1} 완료"
        elif upgrade_key == "budget":
            self.max_budget += 300
            self.budget = min(self.max_budget, self.budget + 200)
            self.budget_regen_rate += 0.20
            msg = f"예산 지원 Lv.{level + 1} 완료"
        elif upgrade_key == "materials":
            self.max_materials += 100
            self.materials = min(self.max_materials, self.materials + 60)
            self.materials_regen_rate += 0.12
            msg = f"물자 확보 Lv.{level + 1} 완료"
        elif upgrade_key == "command":
            self.max_command_points += 1
            self.command_points = self.max_command_points
            msg = f"지휘 보강 Lv.{level + 1} 완료"
        else:
            msg = f"{upgrade['name']} 구매 완료"

        self.play_click_sound()
        self.add_popup(f"{msg} (-{cost} 코인)", (180, 255, 180), 2.0)

    def cycle_focus(self, delta: int = 1):
        unresolved = [d for d in self.active_disasters if not d.resolved]
        if not unresolved:
            self.focus_index = 0
            return
        self.focus_index = (self.focus_index + delta) % len(unresolved)

    def get_action_button(self, action_key: str) -> Button | None:
        for btn in self.play_buttons:
            if btn.command_key == action_key:
                return btn
        return None

    def get_district_label(self, district: str) -> str:
        return {
            "residential": "주거",
            "industrial": "산업",
            "park": "공원",
            "hospital": "병원",
            "police": "경찰",
        }.get(district, district)

    def get_current_objective_status(self) -> tuple[int, int, bool, bool]:
        objective = self.difficulty_objectives.get(self.difficulty, {"rescues": 250, "deaths": 120})
        rescue_target = objective["rescues"]
        death_limit = objective["deaths"]
        rescue_ok = self.rescued_citizens >= rescue_target
        death_ok = self.total_deaths <= death_limit
        return rescue_target, death_limit, rescue_ok, death_ok

    def wrap_text(self, text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
        return lines

    def get_action_adjustment(self, inst: DisasterInstance, action_key: str) -> tuple[float, float, list[str]]:
        rescue_mult = 1.0
        death_mult = 1.0
        notes: list[str] = []
        disaster_type = inst.disaster.type_id

        if action_key != "no_action":
            if disaster_type == "earthquake":
                if action_key == self.button_heli.command_key:
                    rescue_mult *= 1.35
                    death_mult *= 0.72
                    notes.append("공중 구조 적합")
                elif action_key == self.button_medical.command_key:
                    rescue_mult *= 1.25
                    death_mult *= 0.74
                    notes.append("응급 치료 유리")
                elif action_key == self.button_rescue.command_key:
                    rescue_mult *= 1.12
                    death_mult *= 0.92
                elif action_key == self.button_fire.command_key:
                    rescue_mult *= 0.78
                    death_mult *= 1.22
                    notes.append("소방 대응 비효율")
            elif disaster_type == "flood":
                if action_key == self.button_heli.command_key:
                    rescue_mult *= 1.35
                    death_mult *= 0.68
                    notes.append("고립 구역 구조")
                elif action_key == self.button_police.command_key:
                    rescue_mult *= 1.18
                    death_mult *= 0.82
                    notes.append("차량 통제 효과")
                elif action_key == self.button_medical.command_key:
                    rescue_mult *= 1.10
                    death_mult *= 0.88
                elif action_key == self.button_fire.command_key:
                    rescue_mult *= 0.72
                    death_mult *= 1.18
            elif disaster_type == "blizzard":
                if action_key == self.button_medical.command_key:
                    rescue_mult *= 1.30
                    death_mult *= 0.68
                    notes.append("저체온 환자 치료")
                elif action_key == self.button_police.command_key:
                    rescue_mult *= 1.18
                    death_mult *= 0.80
                    notes.append("도로 통제 효과")
                elif action_key == self.button_heli.command_key:
                    rescue_mult *= 0.78
                    death_mult *= 1.14
            elif disaster_type == "wildfire":
                if action_key == self.button_fire.command_key:
                    rescue_mult *= 1.45
                    death_mult *= 0.60
                    notes.append("화재 진압 최적")
                elif action_key == self.button_heli.command_key:
                    rescue_mult *= 1.22
                    death_mult *= 0.76
                elif action_key == self.button_police.command_key:
                    rescue_mult *= 0.92
                    death_mult *= 1.04

        if inst.intel_level > 0:
            if action_key == "no_action":
                death_mult *= max(0.82, 1.0 - 0.08 * inst.intel_level)
            elif action_key != self.button_watch.command_key:
                rescue_mult *= 1.0 + 0.12 * inst.intel_level
                death_mult *= max(0.66, 1.0 - 0.10 * inst.intel_level)
            notes.append(f"현장 분석 {inst.intel_level}단계")

        if inst.evac_ordered:
            if action_key == "no_action":
                death_mult *= 0.82
            elif action_key != self.button_evac.command_key:
                rescue_mult *= 1.05
                death_mult *= 0.76
            notes.append("선제 대피")

        if inst.traffic_control:
            if action_key == "no_action":
                death_mult *= 0.90
            elif action_key != self.button_police.command_key:
                rescue_mult *= 1.08
                death_mult *= 0.90
            notes.append("동선 확보")

        if self.selected_district:
            district_center = pygame.Vector2(self.selected_district.rect.center)
            if district_center.distance_to(inst.position) <= 120:
                rescue_mult *= 1.06
                death_mult *= 0.95
                notes.append("현장 지휘")

                district_type = self.selected_district.district
                if district_type == "park" and disaster_type == "wildfire" and action_key in (
                    self.button_fire.command_key,
                    self.button_heli.command_key,
                ):
                    rescue_mult *= 1.18
                    death_mult *= 0.88
                    notes.append("공원 화재 대응")
                elif district_type == "hospital" and action_key == self.button_medical.command_key:
                    rescue_mult *= 1.18
                    death_mult *= 0.84
                    notes.append("병원 연계")
                elif district_type == "police" and action_key == self.button_police.command_key:
                    rescue_mult *= 1.15
                    death_mult *= 0.86
                    notes.append("경찰 자원 집중")
                elif district_type == "residential" and action_key in (
                    self.button_evac.command_key,
                    self.button_rescue.command_key,
                    self.button_medical.command_key,
                ):
                    rescue_mult *= 1.14
                    death_mult *= 0.90
                    notes.append("주거지 보호")
                elif district_type == "industrial" and action_key == self.button_fire.command_key:
                    rescue_mult *= 1.12
                    death_mult *= 0.88
                    notes.append("산업지대 진압")

        return rescue_mult, death_mult, notes

    def try_prepare_action(self, inst: DisasterInstance, action_key: str) -> bool:
        if action_key == self.button_watch.command_key:
            if inst.intel_level >= 2:
                self.add_popup("현장 분석이 이미 충분합니다.", (170, 215, 255), 1.8)
                return True
            inst.intel_level += 1
            if inst.intel_level == 1:
                self.command_points = min(self.max_command_points, self.command_points + 1)
            self.add_popup(
                f"{inst.disaster.name} 현장 분석 완료: 다음 대응 효율 상승",
                (140, 220, 255),
                2.2,
            )
            self.last_action_summary = f"{inst.disaster.name}: 관찰 모드로 대응 정보 확보"
            return True

        if action_key == self.button_evac.command_key and not inst.evac_ordered:
            inst.evac_ordered = True
            self.add_popup(
                f"{inst.disaster.name} 대피령 발령: 인명 피해 감소",
                (255, 230, 150),
                2.2,
            )
            self.last_action_summary = f"{inst.disaster.name}: 대피령 선행"
            return True

        if (
            action_key == self.button_police.command_key
            and not inst.traffic_control
            and inst.disaster.type_id in ("earthquake", "flood", "blizzard")
        ):
            inst.traffic_control = True
            self.add_popup(
                f"{inst.disaster.name} 교통 통제: 구조 동선 확보",
                (160, 180, 255),
                2.2,
            )
            self.last_action_summary = f"{inst.disaster.name}: 교통 통제 선행"
            return True

        return False

    def get_recommended_action(self, inst: DisasterInstance) -> tuple[str | None, float]:
        best_action = None
        best_value = float("-inf")
        for action_key, outcome in inst.disaster.action_outcomes.items():
            if action_key == "no_action":
                continue
            if action_key == self.button_watch.command_key and inst.intel_level < 2:
                value = 62 + inst.disaster.severity * 30 - inst.intel_level * 16
                if value > best_value:
                    best_action = action_key
                    best_value = value
                continue
            if action_key == self.button_evac.command_key and not inst.evac_ordered:
                value = 54 + inst.disaster.severity * 28
                if inst.disaster.type_id in ("earthquake", "flood", "wildfire"):
                    value += 14
                if value > best_value:
                    best_action = action_key
                    best_value = value
                continue
            if (
                action_key == self.button_police.command_key
                and not inst.traffic_control
                and inst.disaster.type_id in ("earthquake", "flood", "blizzard")
            ):
                value = 52 + inst.disaster.severity * 24
                if value > best_value:
                    best_action = action_key
                    best_value = value
                continue
            death_low, death_high = outcome["death_range"]
            rescue_low, rescue_high = outcome["rescue_range"]
            avg_deaths = (death_low + death_high) * 0.5
            avg_rescues = (rescue_low + rescue_high) * 0.5
            rescue_mult, death_mult, _ = self.get_action_adjustment(inst, action_key)
            avg_deaths *= death_mult
            avg_rescues *= rescue_mult
            value = avg_rescues * 10 - avg_deaths * 15
            if value > best_value:
                best_action = action_key
                best_value = value
        return best_action, best_value

    def format_action_label(self, action_key: str) -> str:
        """화면에 보여줄 액션 이름을 사람이 읽기 좋게 바꾼다."""
        if action_key == "no_action":
            return "대응 없음"
        return action_key

    def get_chain_group(self, inst: DisasterInstance) -> list[DisasterInstance]:
        """연쇄로 연결된 재난 묶음을 반환한다.

        - 지진이 원인인 경우: 원본 지진 + 파생 재난
        - 파생 재난인 경우: 원본 지진 + 해당 파생 재난
        """
        group: list[DisasterInstance] = []

        def add_target(target: DisasterInstance | None):
            if target and target in self.active_disasters and not target.resolved and target not in group:
                group.append(target)

        if inst.is_chain_disaster:
            add_target(inst.chain_source)
            add_target(inst)
        else:
            add_target(inst)
            for other in self.active_disasters:
                if other.is_chain_disaster and other.chain_source is inst:
                    add_target(other)

        return group

    def trigger_action(self, action_key: str):
        if self.evac_mode_active:
            self.add_popup("대피 모드에서는 명령을 사용할 수 없습니다.", (220, 220, 255), 1.6)
            return

        focused = self.get_focused_disaster()
        if not focused:
            self.add_popup("현재 대응할 재난이 없습니다.", (255, 220, 120))
            return

        if action_key == self.button_watch.command_key and focused.intel_level >= 2:
            self.add_popup("현장 분석이 이미 완료된 상태입니다.", (170, 215, 255))
            return

        # 자원 확인
        if not self.can_afford_action(action_key):
            cost = self.get_action_resource_cost(action_key)
            missing = []
            if self.budget < cost["budget"]:
                missing.append("예산")
            if self.manpower < cost["manpower"]:
                missing.append("인력")
            if self.materials < cost["materials"]:
                missing.append("물자")
            self.add_popup(f"자원 부족: {', '.join(missing)}", (255, 120, 120), 2.0)
            return

        cost = self.command_costs.get(action_key, 0)
        timer = self.command_timers.get(action_key, 0.0)
        if timer > 0:
            self.add_popup(f"{action_key}: {int(timer) + 1}초 후 재사용", (255, 200, 80))
            return
        if self.command_points < cost:
            self.add_popup("명령 포인트가 부족합니다.", (255, 120, 120))
            return

        # 자원과 명령 포인트 소모
        self.spend_resources(action_key)
        self.command_points -= cost
        self.command_timers[action_key] = self.command_cooldowns.get(action_key, 0.0)
        self.play_click_sound()

        targets = self.get_chain_group(focused)
        if len(targets) > 1:
            self.add_popup("연쇄 재난 동시 대응!", (255, 220, 120), 1.8)

        # 선행 조치(대피령/관찰/교통통제)는 묶음 전체에 적용할 수 있다.
        if len(targets) == 1 and self.try_prepare_action(focused, action_key):
            return

        resolved_targets: list[DisasterInstance] = []
        for target in targets:
            if target in self.active_disasters and not target.resolved:
                if self.try_prepare_action(target, action_key):
                    continue
                self.apply_disaster_outcome(target, action_key)
                if target.resolved:
                    resolved_targets.append(target)

        for target in resolved_targets:
            if target in self.active_disasters:
                self.active_disasters.remove(target)

        unresolved = [d for d in self.active_disasters if not d.resolved]
        if unresolved:
            self.focus_index %= len(unresolved)
        else:
            self.focus_index = 0

    def get_difficulty_factor(self) -> float:
        elapsed = time.time() - self.start_time
        t = min(1.0, elapsed / self.total_time_limit)
        base = 1.0 + 0.9 * t  # 종료 시점에 1.9배 정도
        return base * getattr(self, "difficulty_multiplier", 1.0)

    def get_scaled_weights(self) -> list[float]:
        factor = self.get_difficulty_factor()
        e, f, fl, none = self.base_disaster_weights
        e *= factor
        f *= factor
        fl *= factor
        none *= max(0.2, 1.5 - factor)
        s = e + f + fl + none
        if s <= 0:
            return self.base_disaster_weights
        return [e / s, f / s, fl / s, none / s]

    def get_scaled_damage_range(self, base_range: tuple[int, int]) -> tuple[int, int]:
        factor = self.get_difficulty_factor()
        low, high = base_range
        bonus = int((factor - 1.0) * 30)
        return max(0, low), max(0, high + bonus)

    def get_action_resource_cost(self, action: str) -> dict:
        """행동별 자원 소모량을 반환한다."""
        costs = {
            "대피령": {"budget": 70, "manpower": 10, "materials": 50},
            "구조대 파견": {"budget": 110, "manpower": 20, "materials": 30},
            "소방대 투입": {"budget": 150, "manpower": 15, "materials": 80},
            "의료 지원": {"budget": 100, "manpower": 25, "materials": 40},
            "헬기 구조": {"budget": 220, "manpower": 5, "materials": 20},
            "경찰 통제": {"budget": 60, "manpower": 15, "materials": 10},
            "관찰 모드": {"budget": 0, "manpower": 0, "materials": 0},
        }
        return costs.get(action, {"budget": 0, "manpower": 0, "materials": 0})

    def can_afford_action(self, action: str) -> bool:
        """행동에 필요한 자원이 있는지 확인한다."""
        cost = self.get_action_resource_cost(action)
        return (self.budget >= cost["budget"] and 
                self.manpower >= cost["manpower"] and 
                self.materials >= cost["materials"])

    def spend_resources(self, action: str):
        """행동에 필요한 자원을 소모한다."""
        cost = self.get_action_resource_cost(action)
        self.budget = max(0, self.budget - cost["budget"])
        self.manpower = max(0, self.manpower - cost["manpower"])
        self.materials = max(0, self.materials - cost["materials"])

    def update_resources(self, dt: float):
        """자원을 재생한다."""
        self.budget = min(self.max_budget, self.budget + self.budget_regen_rate * dt)
        self.manpower = min(self.max_manpower, self.manpower + self.manpower_regen_rate * dt)
        self.materials = min(self.max_materials, self.materials + self.materials_regen_rate * dt)

    ###########################################################
    # 시민 / 구조대 / 재난 보조 유틸
    ###########################################################

    def is_blizzard_active(self) -> bool:
        """현재 활성화된 폭설 재난이 있는지 여부."""
        return any(d.disaster.type_id == "blizzard" for d in self.active_disasters)

    def get_nearest_active_disaster(self, pos: pygame.Vector2) -> tuple[DisasterInstance | None, float]:
        """지정 위치에서 가장 가까운 활성 재난과 거리를 반환."""
        nearest = None
        best = float("inf")
        for inst in self.active_disasters:
            d = (inst.position - pos).length()
            if d < best:
                best = d
                nearest = inst
        return nearest, best

    def get_nearest_rescue_team(self, pos: pygame.Vector2) -> tuple[RescueTeam | None, float]:
        nearest = None
        best = float("inf")
        for team in self.rescue_teams:
            d = (team.pos - pos).length()
            if d < best:
                best = d
                nearest = team
        return nearest, best

    def get_nearest_danger_citizen(self, pos: pygame.Vector2) -> Citizen | None:
        """위험(DANGER/INJURED) 상태의 시민 중 가장 가까운 대상."""
        nearest = None
        best = float("inf")
        for c in self.citizens_visual:
            if not c.alive or c.state in ("RESCUED", "NORMAL") or c.controlled_by_player:
                continue
            d = (c.pos - pos).length()
            if d < best:
                best = d
                nearest = c
        return nearest

    def is_building_blocked(self, pos: pygame.Vector2, padding: int = 3) -> bool:
        point_rect = pygame.Rect(int(pos.x) - padding, int(pos.y) - padding, padding * 2, padding * 2)
        for building in self.buildings:
            if building.collapsed:
                continue
            if building.rect.inflate(4, 4).colliderect(point_rect):
                return True
        return False

    def is_river_blocked(self, pos: pygame.Vector2) -> bool:
        point = (pos.x, pos.y)
        in_river = any(zone.collidepoint(point) for zone in getattr(self, "river_zones", []))
        if not in_river:
            return False
        return not any(zone.collidepoint(point) for zone in getattr(self, "bridge_zones", []))

    def is_position_blocked(self, pos: pygame.Vector2) -> bool:
        return self.is_river_blocked(pos) or self.is_building_blocked(pos)

    def get_nearest_evac_center(self, pos: pygame.Vector2) -> pygame.Vector2 | None:
        if not self.evac_zones:
            return None
        nearest = None
        best = float("inf")
        for zone in self.evac_zones:
            center = pygame.Vector2(zone.rect.center)
            d = (center - pos).length()
            if d < best:
                best = d
                nearest = center
        return nearest

    def rescue_citizen(self, citizen: Citizen):
        """
        Called when rescue team rescues citizen.
        - Injured citizen rescue: +80
        - Normal citizen rescue: +50
        Move citizen to nearest evacuation zone and mark as RESCUED.
        """
        if not citizen.alive:
            return
        if citizen.rescored:
            citizen.state = "RESCUED"
            return

        if citizen.state == "INJURED":
            self.score += 10
        else:
            self.score += 10

        target = self.get_nearest_evac_center(citizen.pos)
        if target is not None:
            citizen.pos.update(target.x, target.y)
        citizen.state = "RESCUED"
        citizen.rescored = True
        self.rescued_citizens += 1
        self.total_rescues += 1
        self.coins += 1
        self.total_coins_earned += 1

    def get_nearest_evac_zone(self, pos: pygame.Vector2):
        if not self.evac_zones:
            return None
        nearest = None
        best = float("inf")
        for zone in self.evac_zones:
            center = pygame.Vector2(zone.rect.center)
            dist = (center - pos).length()
            if dist < best:
                best = dist
                nearest = zone
        return nearest

    def find_evac_spawn_citizen(self) -> Citizen | None:
        """대피 모드에서 조작할 시민을 하나 고른다."""
        candidates = [
            c for c in self.citizens_visual
            if c.alive and not c.rescored and not c.controlled_by_player and c.state != "RESCUED"
        ]
        if not candidates:
            return None

        anchor = pygame.Vector2(WIDTH * 0.5, HEIGHT * 0.55)
        focused = self.get_focused_disaster()
        if focused:
            anchor = pygame.Vector2(focused.position)
        elif self.selected_district:
            anchor = pygame.Vector2(self.selected_district.rect.center)

        if self.selected_district:
            inside = [c for c in candidates if self.selected_district.rect.collidepoint(c.pos)]
            if inside:
                candidates = inside

        candidates.sort(key=lambda c: (c.pos - anchor).length_squared())
        return candidates[0]

    def exit_evac_mode(self, message: str = "대피 모드를 종료했습니다."):
        if self.evac_player_citizen:
            self.evac_player_citizen.controlled_by_player = False
        self.evac_player_citizen = None
        if self.evac_mode_active:
            self.evac_mode_active = False
            self.add_popup(message, (180, 220, 255), 1.4)

    def toggle_evac_mode(self):
        if self.state != STATE_PLAYING or self.paused or self.shop_open:
            return

        if self.evac_mode_active:
            self.exit_evac_mode()
            return

        citizen = self.find_evac_spawn_citizen()
        if not citizen:
            self.add_popup("대피시킬 시민이 없습니다.", (255, 160, 160), 1.8)
            return

        self.evac_player_citizen = citizen
        self.evac_player_citizen.controlled_by_player = True
        self.evac_mode_active = True
        self.add_popup("대피 모드 시작: 방향키/WASD로 이동, E로 종료", (255, 230, 150), 2.2)

        if self.get_nearest_evac_zone(self.evac_player_citizen.pos):
            self.last_action_summary = "대피 모드: 시민 직접 조작"

    def update_evac_player(self, dt: float):
        citizen = self.evac_player_citizen
        if not self.evac_mode_active or not citizen or not citizen.alive or citizen.rescored:
            return

        keys = pygame.key.get_pressed()
        move = pygame.Vector2(0, 0)
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            move.x -= 1
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            move.x += 1
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            move.y -= 1
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            move.y += 1

        speed = 145.0
        if citizen.state == "INJURED":
            speed *= 0.72
        if self.is_blizzard_active():
            speed *= 0.78

        if move.length_squared() > 0:
            move = move.normalize()
            candidate = citizen.pos + move * speed * dt
            candidate.x = max(20, min(WIDTH - 280, candidate.x))
            candidate.y = max(90, min(HEIGHT - 152, candidate.y))

            if self.is_position_blocked(candidate):
                alt_x = pygame.Vector2(citizen.pos.x + move.x * speed * dt, citizen.pos.y)
                alt_y = pygame.Vector2(citizen.pos.x, citizen.pos.y + move.y * speed * dt)
                if not self.is_position_blocked(alt_x):
                    candidate = alt_x
                elif not self.is_position_blocked(alt_y):
                    candidate = alt_y
                else:
                    candidate = citizen.pos
            citizen.pos = candidate

        # 대피 구역 도착 시 자동 구조 처리
        nearest_zone = self.get_nearest_evac_zone(citizen.pos)
        if nearest_zone and nearest_zone.rect.collidepoint(citizen.pos.x, citizen.pos.y):
            self.rescue_citizen(citizen)
            citizen.controlled_by_player = False
            self.evac_player_citizen = None
            self.evac_mode_active = False
            self.evac_mode_successes += 1
            self.score += 15
            self.add_popup("대피 성공! 안전 구역에 도착했습니다.", (150, 255, 170), 2.0)
            self.last_action_summary = "대피 모드: 시민 1명 안전 구역 도착"

    ###########################################################
    # 재난 발생/처리
    ###########################################################

    def roll_disaster(self) -> Disaster:
        weights = self.get_scaled_weights()
        r = random.random()
        cum = 0.0
        idx = len(weights) - 1
        for i, w in enumerate(weights):
            cum += w
            if r <= cum:
                idx = i
                break
        return self.disasters[idx]

    def random_disaster_position(self) -> pygame.Vector2:
        for _ in range(30):
            x = random.randint(300, WIDTH - 320)
            y = random.randint(110, HEIGHT - 210)
            return pygame.Vector2(x, y)
        return pygame.Vector2(WIDTH // 2, HEIGHT // 2 - 20)

    def try_spawn_chain_disaster(self, source_disaster: DisasterInstance, dt: float):
        """Try to spawn chain disaster after earthquake."""
        if source_disaster.disaster.type_id != "earthquake":
            return
            
        # Check chain disaster cooldown
        self.last_chain_time -= dt
        if self.last_chain_time > 0:
            return
            
        # Check chain disaster probability
        if random.random() > self.chain_disaster_chance:
            return
            
        # Select chain disaster type (fire or flood)
        chain_types = ["wildfire", "flood"]
        chain_type = random.choice(chain_types)
        
        # Spawn chain disaster near original disaster
        offset_angle = random.uniform(0, 2 * math.pi)
        offset_distance = random.uniform(60, 120)
        chain_pos = source_disaster.position + pygame.Vector2(
            math.cos(offset_angle) * offset_distance,
            math.sin(offset_angle) * offset_distance
        )
        
        # Adjust to stay within screen bounds
        chain_pos.x = max(300, min(WIDTH - 320, chain_pos.x))
        chain_pos.y = max(110, min(HEIGHT - 210, chain_pos.y))
        
        # Create chain disaster
        for disaster in self.disasters:
            if disaster.type_id == chain_type:
                chain_instance = DisasterInstance(disaster, chain_pos)
                chain_instance.is_chain_disaster = True
                chain_instance.chain_source = source_disaster
                self.active_disasters.append(chain_instance)
                
                # Chain disaster notification
                self.add_popup("⚠️ 연쇄 재난 발생!", (255, 150, 100), 3.0)
                self.play_warning_sound()
                
                # Set cooldown
                self.last_chain_time = self.chain_cooldown_time
                break

    def spawn_disaster(self):
        """Create new disaster and start warning sequence."""
        disaster = self.roll_disaster()
        if disaster.type_id == "none":
            # Don't show popup if nothing happens
            return

        if len(self.active_disasters) >= self.max_active_disasters:
            return

        # 재난별 시작 위치
        if disaster.type_id == "flood":
            # 강 주변에서 시작하도록 y 좌표를 강 근처로 보정
            pos = self.random_disaster_position()
            pos.y = pos.y * 0.0 + HEIGHT * 0.3 + random.uniform(-40, 40)
        elif disaster.type_id == "wildfire":
            # 공원/녹지 블록(park 타입 건물)에서 시작
            park_buildings = [b for b in self.buildings if b.district == "park"]
            if park_buildings:
                b = random.choice(park_buildings)
                pos = pygame.Vector2(b.rect.center)
            else:
                pos = self.random_disaster_position()
        else:
            pos = self.random_disaster_position()

        instance = DisasterInstance(disaster, pos)

        # 확산형 재난의 초기 반경 및 확산 속도 설정
        if disaster.type_id == "flood":
            instance.radius = 40.0
            instance.spread_speed = 12.0
        elif disaster.type_id == "wildfire":
            instance.radius = 35.0
            instance.spread_speed = 18.0
        elif disaster.type_id == "earthquake":
            instance.radius = 50.0
            instance.spread_speed = 8.0
        else:
            instance.radius = 0.0
            instance.spread_speed = 0.0

        self.active_disasters.append(instance)
        self.focus_index = len([d for d in self.active_disasters if not d.resolved]) - 1

        # 경고음 + 연출
        self.play_warning_sound()
        self.flash_timer = self.flash_duration
        self.alert_timer = self.alert_duration
        self.alert_text = f"{disaster.name} 발생"
        self.alert_subtext = disaster.description
        if disaster.type_id == "earthquake":
            self.alert_color = (255, 120, 120)
            self.shake_intensity = 12.0
            self.shake_timer = 0.0
        elif disaster.type_id == "fire":
            self.alert_color = (255, 180, 120)
        elif disaster.type_id == "flood":
            self.alert_color = (140, 200, 255)
        elif disaster.type_id == "wildfire":
            self.alert_color = (255, 140, 80)
            self.popup_messages.append(
                PopupMessage("⚠ 화재 발생!", (255, 100, 50), 3.0)
            )

    def get_focused_disaster(self) -> DisasterInstance | None:
        """플레이어가 현재 조작할 우선순위 재난(가장 오래된 미해결)을 반환."""
        unresolved = [d for d in self.active_disasters if not d.resolved]
        if not unresolved:
            self.focus_index = 0
            return None
        unresolved.sort(key=lambda d: d.decision_start_time)
        self.focus_index %= len(unresolved)
        return unresolved[self.focus_index]

    def apply_disaster_outcome(self, inst: DisasterInstance, action_key: str):
        """선택/시간초과에 따른 재난 결과 적용."""
        d = inst.disaster
        outcome = d.action_outcomes.get(action_key)
        if not outcome:
            return

        death_range = self.get_scaled_damage_range(outcome["death_range"])
        rescue_range = outcome["rescue_range"]
        rescue_mult, death_mult, notes = self.get_action_adjustment(inst, action_key)

        deaths = int(round(random.randint(*death_range) * death_mult))
        rescues = int(round(random.randint(*rescue_range) * rescue_mult))
        deaths = max(0, deaths)
        rescues = max(0, rescues)

        deaths = min(deaths, self.citizens)
        rescues = min(rescues, self.hospital_capacity, self.citizens - deaths)

        self.citizens -= deaths
        self.total_deaths += deaths
        self.total_rescues += rescues
        self.rescued_citizens += rescues
        if rescues > 0:
            self.coins += rescues
            self.total_coins_earned += rescues
        self.events_handled += 1
        self.score += rescues * 10 - deaths * 15  # 구조 +10, 사망 -15

        # 재난 해결 상태로 설정
        inst.resolved = True
        inst.resolved_action = action_key

        # 건물 피해
        building_damage = random.randint(0, deaths // 10)
        for _ in range(building_damage):
            if self.buildings:
                b = random.choice(self.buildings)
                if not b.collapsed:
                    b.collapsed = True
                    self.score -= 5  # 건물 파괴 -5

        # 시민 아이콘 제거
        self.remove_citizens_visual(inst.position, deaths)

        if action_key == self.button_heli.command_key:
            self.spawn_helicopter(inst.position)
            self.play_rescue_sound()

        if action_key != "no_action":
            if rescues >= deaths:
                result_label = "대응 성공"
                result_color = (160, 255, 170)
            else:
                result_label = "대응 미흡"
                result_color = (255, 170, 170)
            self.add_popup(
                f"{result_label}  +구조 {rescues} / -사망 {deaths}",
                result_color,
                2.0,
            )

        if action_key != "no_action":
            if rescues >= max(1, deaths):
                self.combo_count += 1
                self.combo_timer = self.combo_window
                combo_bonus = self.combo_count * 12
                self.score += combo_bonus
                if self.combo_count >= 2:
                    self.add_popup(f"연속 대응 x{self.combo_count}  +{combo_bonus}", (255, 230, 120), 1.8)
            else:
                self.combo_count = 0
                self.combo_timer = 0.0
        else:
            self.combo_count = 0
            self.combo_timer = 0.0

        action_label = self.format_action_label(action_key)
        msg = f"{d.name} - {action_label} 결과: 사망 {deaths}명, 구조 {rescues}명"
        color = (255, 230, 230) if deaths > rescues else (220, 255, 220)
        self.popup_messages.append(PopupMessage(msg, color, 3.0))
        self.last_action_summary = f"{d.name}: {action_label} | +구조 {rescues} / -사망 {deaths}"

        inst.resolved = True
        inst.resolved_action = action_key
        self.score += 20  # 재난 진압 +20

    def remove_citizens_visual(self, center: pygame.Vector2, deaths: int):
        if deaths <= 0:
            return
        alive = [c for c in self.citizens_visual if c.alive]
        if not alive:
            return
        alive.sort(key=lambda c: (c.pos - center).length_squared())
        remove_count = min(len(alive), deaths // 4 + 1)
        for i in range(remove_count):
            alive[i].alive = False

    def spawn_helicopter(self, target: pygame.Vector2):
        self.helicopter = Helicopter((-80, 80), target)

    ###########################################################
    # HUD / 미니맵 / 연출
    ###########################################################

    def draw_main_hud(self, remaining_time: float):
        """전략 게임 스타일 UI 패널."""
        if self.ui_hidden:
            return
        self.draw_top_banner(remaining_time)
        self.draw_left_panel()
        self.draw_right_panel()
        self.draw_bottom_panel()

    def draw_top_banner(self, remaining_time: float):
        compact_mode = self.alert_timer > 0.2
        # 목표/시간이 중심이 되도록 상단 배너를 발표용 요약판처럼 구성한다.
        banner_height = 86 if compact_mode else 108
        banner_rect = pygame.Rect(270, 10, WIDTH - 540, banner_height)
        banner = pygame.Surface(banner_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(banner, (8, 12, 22, 245), banner.get_rect(), border_radius=12)
        pygame.draw.rect(banner, (140, 160, 190), banner.get_rect(), 1, border_radius=12)

        focused = self.get_focused_disaster()
        rescue_target, death_limit, rescue_ok, death_ok = self.get_current_objective_status()
        mm, ss = int(remaining_time) // 60, int(remaining_time) % 60
        if self.evac_mode_active:
            mode_label = "대피 모드"
            goal_body = f"시민 1명 안전 구역 도착 ({self.evac_mode_successes}명 완료)"
        else:
            mode_label = "지휘 모드"
            goal_body = f"구조 {rescue_target}명 / 사망 {death_limit}명 이하"

        mode_text = self.font_tiny.render(f"현재 모드: {mode_label}", True, (240, 245, 255))
        banner.blit(mode_text, (16, 6))

        if focused:
            focus_text = f"포커스: {focused.disaster.name}"
            if len(self.get_chain_group(focused)) > 1:
                focus_text += " | 연쇄 대응"
        else:
            focus_text = "포커스: 없음"
        focus_line = self.font_tiny.render(focus_text, True, (205, 215, 235))
        banner.blit(focus_line, (16, 24))

        goal_font = self.font_tiny
        goal_prefix = self.font_tiny.render("목표", True, (255, 235, 180))
        goal_text = goal_font.render(goal_body, True, (255, 235, 180))
        time_prefix = self.font_tiny.render("시간", True, (220, 235, 255))
        time_text = self.font_small.render(f"{mm:02d}:{ss:02d}", True, (220, 235, 255))

        right_col_x = banner_rect.width - 16
        banner.blit(goal_prefix, (right_col_x - goal_prefix.get_width(), 22))
        banner.blit(goal_text, (right_col_x - goal_text.get_width(), 38))
        banner.blit(time_prefix, (right_col_x - time_prefix.get_width(), 58))
        banner.blit(time_text, (right_col_x - time_text.get_width(), 70))

        if not compact_mode:
            summary = self.font_tiny.render(self.last_action_summary, True, (205, 215, 235))
            banner.blit(summary, (16, 50))
            if self.combo_count > 1 and self.combo_timer > 0:
                combo = self.font_tiny.render(f"연속 대응 x{self.combo_count}", True, (255, 225, 120))
                combo_rect = combo.get_rect(topright=(banner_rect.width - 16, 50))
                banner.blit(combo, combo_rect)
            if self.evac_mode_active:
                evac_tip = self.font_tiny.render("E 종료 | 방향키/WASD 이동", True, (255, 235, 150))
                evac_rect = evac_tip.get_rect(topright=(banner_rect.width - 16, 50))
                banner.blit(evac_tip, evac_rect)
            elif self.tutorial_hint_timer > 0:
                tutorial_tip = self.font_tiny.render("안내: TAB 포커스 / 1~7 대응 / E 대피 / B 상점", True, (255, 235, 150))
                banner.blit(tutorial_tip, (16, 74))

        self.screen.blit(banner, banner_rect.topleft)

    def draw_left_panel(self):
        """좌측 패널: 도시 정보, 재난 정보, 시민 상태."""
        panel_w = 230
        base_x = 10 - (1 - self.ui_animation_progress) * panel_w
        panel_rect = pygame.Rect(base_x, 10, panel_w, HEIGHT - 200)
        panel_surf = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel_surf, (4, 6, 12, 235), panel_surf.get_rect(), border_radius=8)
        pygame.draw.rect(panel_surf, (120, 120, 135), panel_surf.get_rect(), 1, border_radius=8)

        y = 10
        title_color = (200, 200, 255)
        text_color = (255, 255, 255)

        # 도시 정보
        title = self.font_tiny.render("도시 정보", True, title_color)
        panel_surf.blit(title, (10, y))
        y += 38
        diff_label = self.difficulty_names.get(self.difficulty, self.difficulty)
        high_score = self.high_scores.get(self.difficulty, 0)
        info = [
            f"난이도: {diff_label}",
            f"최고 점수: {high_score:,}",
            f"남은 시민: {self.citizens}",
            f"구조된 시민: {self.rescued_citizens}",
            f"사망: {self.total_deaths}",
            f"점수: {self.calculate_final_score()}",
        ]
        for line in info:
            surf = self.font_tiny.render(line, True, text_color)
            panel_surf.blit(surf, (10, y))
            y += 18

        y += 10
        # 재난 정보
        title = self.font_tiny.render("재난 정보", True, title_color)
        panel_surf.blit(title, (10, y))
        y += 38
        disaster_counts = {}
        for inst in self.active_disasters:
            if not inst.resolved:
                disaster_counts[inst.disaster.name] = disaster_counts.get(inst.disaster.name, 0) + 1
        if not disaster_counts:
            surf = self.font_tiny.render("현재 재난: 없음", True, text_color)
            panel_surf.blit(surf, (10, y))
            y += 18
        else:
            total = sum(disaster_counts.values())
            for name, count in disaster_counts.items():
                surf = self.font_tiny.render(f"{name}: {count}", True, text_color)
                panel_surf.blit(surf, (10, y))
                y += 18

            # 활성 재난 / 대응 시간
            focused = self.get_focused_disaster()
            surf = self.font_tiny.render(f"활성 재난: {total} / {self.max_active_disasters}", True, text_color)
            panel_surf.blit(surf, (10, y))
            y += 18

            if focused:
                now = self.pause_started_at if self.paused else time.time()
                remaining = max(0.0, self.disaster_decision_time_limit - (now - focused.decision_start_time))
                surf = self.font_tiny.render(f"{focused.disaster.name} 대응: {remaining:.1f}s", True, text_color)
                panel_surf.blit(surf, (10, y))
                y += 18
                recommended, _ = self.get_recommended_action(focused)
                if recommended:
                    surf = self.font_tiny.render(f"추천 명령: {recommended}", True, (180, 255, 180))
                    panel_surf.blit(surf, (10, y))
                    y += 18

        y += 10
        title = self.font_tiny.render("작전 목표", True, title_color)
        panel_surf.blit(title, (10, y))
        y += 38
        rescue_target, death_limit, rescue_ok, death_ok = self.get_current_objective_status()
        objective_lines = [
            (f"구조 목표: {self.rescued_citizens}/{rescue_target}", (180, 255, 180) if rescue_ok else text_color),
            (f"사망 제한: {self.total_deaths}/{death_limit}", (180, 255, 180) if death_ok else (255, 160, 160)),
        ]
        for line, color in objective_lines:
            surf = self.font_tiny.render(line, True, color)
            panel_surf.blit(surf, (10, y))
            y += 18

        # 시민 상태
        y += 16
        title = self.font_tiny.render("시민 상태", True, title_color)
        panel_surf.blit(title, (10, y))
        y += 38
        states = {"NORMAL": 0, "INJURED": 0, "DANGER": 0, "RESCUED": 0, "SAFE": 0}
        for c in self.citizens_visual:
            if c.alive:
                states[c.state] = states.get(c.state, 0) + 1
        for state, count in states.items():
            surf = self.font_tiny.render(f"{state}: {count}", True, text_color)
            panel_surf.blit(surf, (10, y))
            y += 18

        self.screen.blit(panel_surf, panel_rect.topleft)

    def draw_right_panel(self):
        """우측 패널: 선택된 지역 정보 + 미니맵."""
        panel_w = 230
        base_x = WIDTH - 240 + (1 - self.ui_animation_progress) * panel_w
        panel_rect = pygame.Rect(base_x, 10, panel_w, HEIGHT - 200)
        panel_surf = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel_surf, (4, 6, 12, 235), panel_surf.get_rect(), border_radius=8)
        pygame.draw.rect(panel_surf, (120, 120, 135), panel_surf.get_rect(), 1, border_radius=8)

        y = 10
        title_color = (200, 200, 255)
        text_color = (255, 255, 255)

        title = self.font_tiny.render("선택된 지역", True, title_color)
        panel_surf.blit(title, (10, y))
        y += 30

        district_card = pygame.Rect(10, y, panel_rect.width - 20, 128)
        pygame.draw.rect(panel_surf, (18, 28, 42, 210), district_card, border_radius=12)
        pygame.draw.rect(panel_surf, (90, 110, 140), district_card, 1, border_radius=12)
        if self.selected_district:
            info = [
                f"구역  {self.get_district_label(self.selected_district.district)}",
                f"좌표  {self.selected_district.rect.centerx}, {self.selected_district.rect.centery}",
                f"시민  {len([c for c in self.citizens_visual if self.selected_district.rect.collidepoint(c.pos)])}명",
                f"위험  {'높음' if any(inst.position.distance_to(pygame.Vector2(self.selected_district.rect.center)) < 100 for inst in self.active_disasters) else '낮음'}",
                f"상태  {'붕괴' if self.selected_district.collapsed else '정상'}",
            ]
            for line in info:
                wrapped = self.wrap_text(line, self.font_tiny, district_card.width - 24)
                for part in wrapped:
                    surf = self.font_tiny.render(part, True, text_color)
                    panel_surf.blit(surf, (20, y))
                    y += 18
        else:
            lines = [
                "맵을 클릭해 지역을 선택하세요.",
                "선택한 구역의 위험도와",
                "시민 밀집도를 여기서 확인합니다.",
            ]
            for line in lines:
                wrapped = self.wrap_text(line, self.font_tiny, district_card.width - 24)
                for part in wrapped:
                    surf = self.font_tiny.render(part, True, (210, 218, 235))
                    panel_surf.blit(surf, (20, y))
                    y += 18
        y = district_card.bottom + 18

        focused = self.get_focused_disaster()
        focus_card = pygame.Rect(10, y, panel_rect.width - 20, 142)
        pygame.draw.rect(panel_surf, (18, 28, 42, 210), focus_card, border_radius=12)
        pygame.draw.rect(panel_surf, (90, 110, 140), focus_card, 1, border_radius=12)
        if focused:
            title = self.font_tiny.render("집중 대응", True, title_color)
            panel_surf.blit(title, (18, y + 10))
            y += 38
            recommended, expected = self.get_recommended_action(focused)
            prep_state = []
            if focused.intel_level:
                prep_state.append(f"분석 {focused.intel_level}")
            if focused.evac_ordered:
                prep_state.append("대피령")
            if focused.traffic_control:
                prep_state.append("교통통제")
            focus_lines = [
                f"재난  {focused.disaster.name}",
                f"좌표  {int(focused.position.x)}, {int(focused.position.y)}",
                f"추천  {recommended or '-'}",
                f"효율  {int(expected)}",
            ]
            for line in focus_lines:
                wrapped = self.wrap_text(line, self.font_tiny, focus_card.width - 24)
                for part in wrapped:
                    surf = self.font_tiny.render(part, True, text_color)
                    panel_surf.blit(surf, (20, y))
                    y += 18
        else:
            title = self.font_tiny.render("집중 대응", True, title_color)
            panel_surf.blit(title, (18, y + 10))
            empty = self.font_tiny.render("현재 집중할 재난이 없습니다.", True, (210, 218, 235))
            panel_surf.blit(empty, (20, y + 46))
            y += 124

        # 미니맵
        y = focus_card.bottom + 18
        map_title = self.font_tiny.render("도시 지도", True, title_color)
        panel_surf.blit(map_title, (10, y))
        y += 26
        map_rect = pygame.Rect(10, y, panel_rect.width - 20, 136)
        # 미니맵 배경
        pygame.draw.rect(panel_surf, (20, 30, 40, 200), map_rect, border_radius=6)
        pygame.draw.rect(panel_surf, (140, 140, 160), map_rect, 1, border_radius=6)

        # 미니맵 내부에 도시/재난/구조대 표시
        map_surf = pygame.Surface((map_rect.width - 8, map_rect.height - 8), pygame.SRCALPHA)
        map_surf.fill((0, 0, 0, 0))
        inner_w, inner_h = map_surf.get_size()

        # 도시 (강)
        river_x = int(inner_w * 0.45)
        pygame.draw.rect(map_surf, (50, 110, 170), (river_x, 0, 14, inner_h))

        # 재난 위치
        t = time.time()
        blink = (math.sin(t * 6.0) + 1) * 0.5
        radius = 2 + int(blink * 4)
        focused = self.get_focused_disaster()
        for inst in self.active_disasters:
            mx = int((inst.position.x / WIDTH) * inner_w)
            my = int(((inst.position.y - 70) / (HEIGHT - 70)) * inner_h)
            color = (255, 220, 120) if inst is focused else (255, 80, 80)
            rad = radius + 2 if inst is focused else radius
            pygame.draw.circle(map_surf, color, (mx, my), rad)

        # 구조대 위치
        for team in self.rescue_teams:
            mx = int((team.pos.x / WIDTH) * inner_w)
            my = int(((team.pos.y - 70) / (HEIGHT - 70)) * inner_h)
            pygame.draw.circle(map_surf, (0, 255, 0), (mx, my), 2)

        # 선택된 지역 위치
        if self.selected_district:
            mx = int((self.selected_district.rect.centerx / WIDTH) * inner_w)
            my = int(((self.selected_district.rect.centery - 70) / (HEIGHT - 70)) * inner_h)
            pygame.draw.circle(map_surf, (255, 255, 0), (mx, my), 3)
            pygame.draw.circle(map_surf, (0, 0, 0), (mx, my), 3, 1)

        panel_surf.blit(map_surf, (map_rect.x + 4, map_rect.y + 4))

        y = map_rect.bottom + 16
        note_rect = pygame.Rect(10, y, panel_rect.width - 20, panel_rect.height - y - 10)
        pygame.draw.rect(panel_surf, (18, 28, 42, 210), note_rect, border_radius=12)
        pygame.draw.rect(panel_surf, (90, 110, 140), note_rect, 1, border_radius=12)
        note_title = self.font_tiny.render("전술 메모", True, title_color)
        panel_surf.blit(note_title, (18, y + 10))
        memo_lines = [
            "대피 모드에서는 시민을",
            "직접 안전 구역으로 이동시킵니다.",
            "구조대는 자동으로 지원하고",
            "지휘는 명령 버튼으로 처리합니다.",
        ]
        for idx, line in enumerate(memo_lines):
            surf = self.font_tiny.render(line, True, (210, 218, 235))
            panel_surf.blit(surf, (20, y + 42 + idx * 20))

        self.screen.blit(panel_surf, panel_rect.topleft)

    def draw_bottom_panel(self):
        """하단 명령 패널."""
        # 패널 위치를 더 아래로 내려서 팝업과 겹치지 않게 함
        base_y = HEIGHT - 176 + (1 - self.ui_animation_progress) * 176
        panel_rect = pygame.Rect(10, base_y, WIDTH - 20, 168)
        panel_surf = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel_surf, (8, 10, 18, 238), panel_surf.get_rect(), border_radius=12)
        pygame.draw.rect(panel_surf, (130, 130, 145), panel_surf.get_rect(), 1, border_radius=12)

        title_color = (200, 200, 255)
        y = 10
        title = self.font_small.render("명령", True, title_color)
        panel_surf.blit(title, (10, y))
        if self.evac_mode_active:
            sub_text = "대피 모드: 방향키/WASD 이동  |  구조는 자동 지원  |  E 종료"
        else:
            sub_text = "숫자키 즉시 발동  |  TAB 포커스 전환 / P 일시정지 / B 상점 / E 대피"
        sub = self.font_tiny.render(sub_text, True, (180, 194, 220))
        panel_surf.blit(sub, (10, 30))

        # 현재 명령 포인트 표시
        cp_text = self.font_tiny.render(
            f"명령 포인트: {int(self.command_points)} / {self.max_command_points}", True, (210, 220, 240)
        )
        cp_bg = cp_text.get_rect()
        cp_bg.topleft = (panel_rect.width - cp_bg.width - 14, 10)
        pygame.draw.rect(panel_surf, (15, 20, 30, 200), cp_bg.inflate(12, 8), border_radius=6)
        pygame.draw.rect(panel_surf, (140, 140, 160), cp_bg.inflate(12, 8), 1, border_radius=6)
        panel_surf.blit(cp_text, (cp_bg.x + 6, cp_bg.y + 4))
        bar_rect = pygame.Rect(10, 52, panel_rect.width - 20, 12)
        pygame.draw.rect(panel_surf, (20, 28, 40), bar_rect, border_radius=6)
        pygame.draw.rect(panel_surf, (100, 120, 150), bar_rect, 1, border_radius=6)
        fill_ratio = 0 if self.max_command_points <= 0 else self.command_points / self.max_command_points
        fill_rect = pygame.Rect(bar_rect.x + 1, bar_rect.y + 1, int((bar_rect.width - 2) * fill_ratio), bar_rect.height - 2)
        if fill_rect.width > 0:
            pygame.draw.rect(panel_surf, (90, 180, 255), fill_rect, border_radius=5)
        self.screen.blit(panel_surf, panel_rect.topleft)

        buttons = [
            self.button_evac,
            self.button_rescue,
            self.button_fire,
            self.button_medical,
            self.button_heli,
            self.button_police,
            self.button_watch,
            self.button_shop,
        ]
        cols = 4
        btn_w = 170
        btn_h = 34
        gap_x = 8
        gap_y = 8
        grid_origin_x = 12
        grid_origin_y = 66

        for index, btn in enumerate(buttons):
            if not btn:
                continue
            # 버튼마다 현재 쿨다운/활성 상태 반영
            if btn is self.button_shop:
                if self.evac_mode_active:
                    btn.cooldown = 0.0
                    btn.cooldown_max = 0.0
                    btn.enabled = False
                    btn.tooltip = "대피 모드에서는 사용할 수 없음"
                else:
                    btn.cooldown = 0.0
                    btn.cooldown_max = 0.0
                    btn.enabled = True
                    btn.tooltip = f"코인 {self.coins}개"
            elif btn.command_key:
                if self.evac_mode_active:
                    btn.cooldown = 0.0
                    btn.cooldown_max = 0.0
                    btn.enabled = False
                else:
                    btn.cooldown = self.command_timers.get(btn.command_key, 0.0)
                    btn.cooldown_max = self.command_cooldowns.get(btn.command_key, btn.cooldown_max)
                    cost = self.command_costs.get(btn.command_key, 0)
                    btn.enabled = self.command_points >= cost and btn.cooldown <= 0.0
                    # 툴팁에 현재 상태 반영
                    if btn.cooldown > 0:
                        btn.tooltip = f"{btn.command_key} (쿨다운 {int(btn.cooldown)+1}s)"
                    else:
                        btn.tooltip = f"{btn.command_key} (포인트 {cost})"
                if self.evac_mode_active:
                    btn.tooltip = "대피 모드에서는 사용할 수 없음"

            row = index // cols
            col = index % cols
            button_x = grid_origin_x + col * (btn_w + gap_x)
            button_y = grid_origin_y + row * (btn_h + gap_y)
            btn.rect.size = (btn_w, btn_h)

            abs_x = panel_rect.x + button_x
            abs_y = panel_rect.y + button_y
            btn.draw(self.screen, abs_x, abs_y)

    def draw_minimap(self):
        """오른쪽 상단 미니맵 패널 + 재난 위치."""
        r = self.minimap_rect
        mm_surf = pygame.Surface(r.size, pygame.SRCALPHA)
        pygame.draw.rect(mm_surf, (5, 10, 20, 210), mm_surf.get_rect(), border_radius=12)
        pygame.draw.rect(mm_surf, (200, 200, 210), mm_surf.get_rect(), 2, border_radius=12)

        map_w, map_h = r.width - 12, r.height - 24
        offset_x, offset_y = 6, 16

        # 강(단순 세로 띠)
        river_x = offset_x + map_w * 0.45
        pygame.draw.rect(
            mm_surf,
            (50, 110, 170),
            (river_x, offset_y, 16, map_h),
        )

        # 시민
        for c in self.citizens_visual:
            if not c.alive:
                continue
            mx = offset_x + (c.pos.x / WIDTH) * map_w
            my = offset_y + ((c.pos.y - 70) / (HEIGHT - 70)) * map_h
            if 0 <= mx < r.width and 0 <= my < r.height:
                pygame.draw.circle(mm_surf, (255, 255, 255), (int(mx), int(my)), 1)

        # 구조대
        for team in self.rescue_teams:
            mx = offset_x + (team.pos.x / WIDTH) * map_w
            my = offset_y + ((team.pos.y - 70) / (HEIGHT - 70)) * map_h
            if 0 <= mx < r.width and 0 <= my < r.height:
                pygame.draw.circle(mm_surf, (0, 255, 0), (int(mx), int(my)), 2)

        # 대피소
        for zone in self.evac_zones:
            mx = offset_x + (zone.rect.centerx / WIDTH) * map_w
            my = offset_y + ((zone.rect.centery - 70) / (HEIGHT - 70)) * map_h
            pygame.draw.rect(mm_surf, (255, 255, 0), (int(mx)-2, int(my)-2, 4, 4))

        if self.evac_mode_active and self.evac_player_citizen:
            px = offset_x + (self.evac_player_citizen.pos.x / WIDTH) * map_w
            py = offset_y + ((self.evac_player_citizen.pos.y - 70) / (HEIGHT - 70)) * map_h
            pygame.draw.circle(mm_surf, (255, 240, 160), (int(px), int(py)), 3)
            pygame.draw.circle(mm_surf, (0, 0, 0), (int(px), int(py)), 3, 1)

        # 선택된 지역 (목표)
        if self.selected_district:
            mx = offset_x + (self.selected_district.rect.centerx / WIDTH) * map_w
            my = offset_y + ((self.selected_district.rect.centery - 70) / (HEIGHT - 70)) * map_h
            pygame.draw.circle(mm_surf, (255, 255, 0), (int(mx), int(my)), 3)
            pygame.draw.circle(mm_surf, (0, 0, 0), (int(mx), int(my)), 3, 1)

        title = self.font_tiny.render("도시 미니맵", True, (230, 230, 250))
        mm_surf.blit(title, (8, 2))

        self.screen.blit(mm_surf, r.topleft)

    def draw_earthquake_background(self):
        if self.shake_intensity <= 0:
            self.screen.fill((32, 54, 80))
            self.screen.blit(self.city_surface, self.camera_offset)
            return
        ox = random.uniform(-self.shake_intensity, self.shake_intensity)
        oy = random.uniform(-self.shake_intensity, self.shake_intensity)
        self.screen.fill((32, 54, 80))
        self.screen.blit(self.city_surface, (ox + self.camera_offset.x, oy + self.camera_offset.y))

    def draw_disaster_effects(self):
        """각 재난 타입에 맞는 아이콘/물결 애니메이션."""
        focused = self.get_focused_disaster()
        for inst in self.active_disasters:
            inst.draw(self.screen, self.camera_offset)
            d = inst.disaster
            pos = inst.position
            if inst is focused:
                pulse = (math.sin(time.time() * 5.5) + 1) * 0.5
                if d.type_id == "flood":
                    ring_radius = int(max(22, inst.radius * 0.22) + pulse * 6)
                else:
                    ring_radius = int(max(32, inst.radius * 0.45) + pulse * 10)
                pygame.draw.circle(self.screen, (255, 230, 120), (int(pos.x + self.camera_offset.x), int(pos.y + self.camera_offset.y)), ring_radius, 3)

            if d.type_id == "wildfire":
                t = time.time()
                pulse = (math.sin(t * 9) + 1) * 0.5
                size = 18 + int(pulse * 6)
                color = (255, int(130 + pulse * 100), int(40 + pulse * 40))
                pts = [
                    (pos.x + self.camera_offset.x, pos.y - size + self.camera_offset.y),
                    (pos.x - size * 0.7 + self.camera_offset.x, pos.y + size * 0.2 + self.camera_offset.y),
                    (pos.x + self.camera_offset.x, pos.y + size + self.camera_offset.y),
                    (pos.x + size * 0.7 + self.camera_offset.x, pos.y + size * 0.2 + self.camera_offset.y),
                ]
                pygame.draw.polygon(self.screen, color, pts)
                pygame.draw.polygon(self.screen, (0, 0, 0), pts, 2)
                # 붉은 빛 오버레이
                overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                overlay.fill((255, 50, 50, int(30 * pulse)))
                self.screen.blit(overlay, (0, 0))

            elif d.type_id == "earthquake":
                center = (int(pos.x + self.camera_offset.x), int(pos.y + self.camera_offset.y))
                pygame.draw.circle(self.screen, (250, 70, 70), center, 22)
                pygame.draw.circle(self.screen, (0, 0, 0), center, 22, 2)
                crack = [
                    (pos.x - 8 + self.camera_offset.x, pos.y - 18 + self.camera_offset.y),
                    (pos.x + 2 + self.camera_offset.x, pos.y - 4 + self.camera_offset.y),
                    (pos.x - 4 + self.camera_offset.x, pos.y + 6 + self.camera_offset.y),
                    (pos.x + 6 + self.camera_offset.x, pos.y + 18 + self.camera_offset.y),
                ]
                pygame.draw.lines(self.screen, (255, 255, 255), False, crack, 3)

            elif d.type_id == "blizzard":
                # 눈 파티클은 별도 처리
                pass

            # 경고 아이콘
            icon_center = (int(pos.x + self.camera_offset.x), int(pos.y + self.camera_offset.y) - 34)
            pygame.draw.circle(self.screen, (255, 80, 80), icon_center, 12)
            pygame.draw.circle(self.screen, (0, 0, 0), icon_center, 12, 2)
            ex = self.font_tiny.render("!", True, (255, 255, 255))
            self.screen.blit(ex, ex.get_rect(center=icon_center))

    def draw_buildings(self):
        for zone in self.evac_zones:
            zone.draw(self.screen, self.camera_offset)
        for b in self.buildings:
            b.draw(self.screen, self.camera_offset)

    def draw_citizens(self):
        for c in self.citizens_visual:
            if c.controlled_by_player:
                continue
            c.draw(self.screen, self.camera_offset)

    def draw_evac_player(self):
        if not self.evac_mode_active or not self.evac_player_citizen:
            return

        citizen = self.evac_player_citizen
        pos = citizen.pos
        shadow = pygame.Surface((72, 72), pygame.SRCALPHA)
        pygame.draw.circle(shadow, (255, 230, 120, 38), (36, 36), 28)
        pygame.draw.circle(shadow, (255, 255, 255, 60), (36, 36), 20, 2)
        self.screen.blit(shadow, shadow.get_rect(center=(int(pos.x + self.camera_offset.x), int(pos.y + self.camera_offset.y))))

        body_color = (255, 245, 180)
        outline = (40, 45, 60)
        pygame.draw.circle(self.screen, body_color, (int(pos.x + self.camera_offset.x), int(pos.y + self.camera_offset.y) - 5), 6)
        pygame.draw.circle(self.screen, outline, (int(pos.x + self.camera_offset.x), int(pos.y + self.camera_offset.y) - 5), 6, 2)
        pygame.draw.polygon(
            self.screen,
            body_color,
            [
                (int(pos.x + self.camera_offset.x), int(pos.y + self.camera_offset.y) + 1),
                (int(pos.x + self.camera_offset.x) - 6, int(pos.y + self.camera_offset.y) + 10),
                (int(pos.x + self.camera_offset.x) + 6, int(pos.y + self.camera_offset.y) + 10),
            ],
        )
        pygame.draw.polygon(
            self.screen,
            outline,
            [
                (int(pos.x + self.camera_offset.x), int(pos.y + self.camera_offset.y) + 1),
                (int(pos.x + self.camera_offset.x) - 6, int(pos.y + self.camera_offset.y) + 10),
                (int(pos.x + self.camera_offset.x) + 6, int(pos.y + self.camera_offset.y) + 10),
            ],
            2,
        )

        nearest_zone = self.get_nearest_evac_zone(pos)
        if nearest_zone:
            zone_center = pygame.Vector2(nearest_zone.rect.center)
            pygame.draw.line(self.screen, (255, 235, 140), pos + self.camera_offset, zone_center + self.camera_offset, 2)
            pygame.draw.circle(self.screen, (255, 235, 140), (int(zone_center.x + self.camera_offset.x), int(zone_center.y + self.camera_offset.y)), 6, 2)

        hint = self.font_tiny.render("대피 중", True, (255, 245, 180))
        self.screen.blit(hint, hint.get_rect(midbottom=(int(pos.x + self.camera_offset.x), int(pos.y + self.camera_offset.y) - 16)))

    def draw_helicopter(self):
        if self.helicopter:
            self.helicopter.draw(self.screen, self.camera_offset)

    def draw_popups(self):
        self.popup_messages = [p for p in self.popup_messages if p.is_alive()]
        while len(self.popup_messages) < 3 and getattr(self, "popup_queue", []):
            popup = self.popup_queue.pop(0)
            popup.start_time = time.time()
            self.popup_messages.append(popup)
        if self.ui_hidden:
            return
        if not self.popup_messages:
            return
        # 팝업은 일정 간격으로만 쌓고, 한 번에 최대 3개만 보인다.
        base_y = 438
        step_y = 30
        visible_popups = self.popup_messages[:3]
        for i, p in enumerate(reversed(visible_popups)):
            alpha = max(0.3, 1.0 - (time.time() - p.start_time) / p.duration)
            # pygame.font.render는 항상 안전한 RGB 3값을 기대하므로 정규화한다.
            try:
                base_color = pygame.Color(*p.color[:3]) if isinstance(p.color, (list, tuple)) else pygame.Color(p.color)
            except Exception:
                base_color = pygame.Color(255, 255, 255)
            color = (
                int(base_color.r),
                int(base_color.g),
                int(base_color.b),
            )
            
            # 중복된 메시지 개수 표시
            display_text = p.text
            if p.count > 1:
                display_text = f"{p.text} x{p.count}"

            try:
                surf = self.font_small.render(display_text, True, color)
            except Exception:
                surf = self.font_small.render(display_text, True, (255, 255, 255))
            rect = surf.get_rect(center=(WIDTH // 2, base_y + i * step_y))
            bg = rect.inflate(20, 10)
            pygame.draw.rect(self.screen, (20, 25, 40), bg, border_radius=8)
            pygame.draw.rect(self.screen, (60, 70, 90), bg, 2, border_radius=8)
            self.screen.blit(surf, rect)

    def add_popup(self, text: str, color, duration: float = 2.0):
        """팝업 메시지를 추가한다. 중복된 메시지는 개수를 늘린다."""
        popup_obj = PopupMessage(text, color, duration)

        # 이미 같은 메시지가 있는지 확인
        for popup in self.popup_messages:
            if popup.text == text and popup.color == color:
                popup.add_duplicate()
                return
        for popup in getattr(self, "popup_queue", []):
            if popup.text == text and popup.color == color:
                popup.add_duplicate()
                return
        
        # 현재 화면에 보여줄 수 있는 팝업이 3개 미만이고 대기열이 비어 있을 때만 즉시 표시
        if len(self.popup_messages) < 3 and not getattr(self, "popup_queue", []):
            self.popup_messages.append(popup_obj)
        else:
            self.popup_queue.append(popup_obj)

    def draw_pause_overlay(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 24, 150))
        self.screen.blit(overlay, (0, 0))

        panel = pygame.Rect(0, 0, 420, 220)
        panel.center = (WIDTH // 2, HEIGHT // 2)
        pygame.draw.rect(self.screen, (16, 24, 40), panel, border_radius=16)
        pygame.draw.rect(self.screen, (150, 170, 200), panel, 2, border_radius=16)

        title = self.font_large.render("PAUSED", True, (240, 245, 255))
        self.screen.blit(title, title.get_rect(center=(panel.centerx, panel.y + 60)))

        lines = [
            "P / ESC : 계속하기",
            "TAB : 다음 재난 포커스",
            "1~7 : 명령 단축키",
        ]
        for idx, line in enumerate(lines):
            surf = self.font_medium.render(line, True, (210, 220, 240))
            self.screen.blit(surf, surf.get_rect(center=(panel.centerx, panel.y + 118 + idx * 30)))

    def draw_shop_overlay(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((4, 8, 18, 180))
        self.screen.blit(overlay, (0, 0))

        panel = pygame.Rect(0, 0, 780, 540)
        panel.center = (WIDTH // 2, HEIGHT // 2)
        pygame.draw.rect(self.screen, (14, 20, 34), panel, border_radius=20)
        pygame.draw.rect(self.screen, (180, 180, 200), panel, 2, border_radius=20)

        title = self.font_medium.render("상점", True, (245, 245, 255))
        self.screen.blit(title, title.get_rect(midtop=(panel.centerx, panel.y + 20)))
        sub = self.font_small.render(
            f"보유 코인 {self.coins}개  |  코인을 사용해 인력과 자원을 강화합니다.",
            True,
            (200, 214, 236),
        )
        self.screen.blit(sub, sub.get_rect(midtop=(panel.centerx, panel.y + 62)))

        card_w = 320
        card_h = 124
        gap_x = 24
        gap_y = 18
        start_x = panel.x + 34
        start_y = panel.y + 116
        entries = [
            ("manpower", (72, 150, 90)),
            ("budget", (150, 125, 60)),
            ("materials", (150, 95, 55)),
            ("command", (70, 110, 160)),
        ]

        for idx, (key, color) in enumerate(entries):
            row = idx // 2
            col = idx % 2
            x = start_x + col * (card_w + gap_x)
            y = start_y + row * (card_h + gap_y)
            btn = self.shop_buttons[idx]
            btn.rect.size = (card_w, card_h)
            btn.tooltip = self.shop_upgrades[key]["desc"]
            btn.enabled = self.can_buy_shop_upgrade(key)
            btn.cooldown = 0.0
            btn.cooldown_max = 0.0
            btn.draw(self.screen, x, y)

            level = self.shop_levels[key]
            upgrade = self.shop_upgrades[key]
            cost = self.get_shop_upgrade_cost(key)
            label = self.font_small.render(f"Lv.{level}  |  가격 {cost} 코인", True, (225, 232, 245))
            self.screen.blit(label, (x + 14, y + 74))
            desc = self.font_tiny.render(upgrade["desc"], True, (190, 200, 218))
            self.screen.blit(desc, (x + 14, y + 96))
            if level >= upgrade["max_level"]:
                done = self.font_tiny.render("MAX", True, (255, 230, 120))
                self.screen.blit(done, done.get_rect(topright=(x + card_w - 14, y + 14)))

        self.shop_buttons[4].rect.size = (120, 42)
        self.shop_buttons[4].draw(self.screen, panel.right - 136, panel.y + 16)

        hint = self.font_tiny.render("클릭으로 구매 | ESC 또는 B로 닫기", True, (180, 194, 220))
        self.screen.blit(hint, hint.get_rect(center=(panel.centerx, panel.bottom - 22)))

    def draw_flash_and_alert(self):
        """붉은 화면 플래시 + 중앙 경고 텍스트 애니메이션."""
        if self.ui_hidden:
            return
        if self.flash_timer > 0:
            t = self.flash_timer / self.flash_duration
            alpha = int(110 * t)
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((255, 40, 40, alpha))
            self.screen.blit(overlay, (0, 0))

        if self.alert_timer > 0 and self.alert_text:
            t = 1.0 - self.alert_timer / self.alert_duration
            alpha = int(245 * min(1.0, 1.08 - t * 0.18))
            title_lines = self.wrap_text(self.alert_text, self.font_small, 360) or [self.alert_text]
            sub_lines = self.wrap_text(self.alert_subtext, self.font_tiny, 360) if self.alert_subtext else []
            sub_lines = sub_lines[:2]

            title_h = 22 * len(title_lines[:1])
            sub_h = 16 * len(sub_lines)
            card_w = 400
            card_h = max(54, 16 + title_h + (6 if sub_lines else 0) + sub_h)
            card_rect = pygame.Rect(0, 0, card_w, card_h)
            # 상단 HUD 바로 아래로 내려 배너가 정보 패널과 겹치지 않게 한다.
            card_rect.midtop = (WIDTH // 2, 168)
            card = pygame.Surface(card_rect.size, pygame.SRCALPHA)
            pygame.draw.rect(card, (18, 24, 36, 255), card.get_rect(), border_radius=16)
            pygame.draw.rect(card, self.alert_color, card.get_rect(), 2, border_radius=18)

            # 상단 배너형으로 정리해 HUD와 겹침을 줄인다.
            icon_box = pygame.Rect(16, 11, 28, 28)
            pygame.draw.rect(card, (255, 255, 255, 20), icon_box, border_radius=12)
            pygame.draw.rect(card, self.alert_color, icon_box, 2, border_radius=12)
            pygame.draw.circle(card, self.alert_color, icon_box.center, 8, 3)
            ex = self.font_tiny.render("!", True, self.alert_color)
            card.blit(ex, ex.get_rect(center=icon_box.center))

            text_x = 48
            text_y = 9
            title = self.font_tiny.render(title_lines[0], True, (248, 245, 250))
            card.blit(title, (text_x, text_y))
            text_y += 19
            if sub_lines:
                text_y += 1
            for line in sub_lines[:3]:
                subtitle = self.font_tiny.render(line, True, (230, 230, 240))
                card.blit(subtitle, (text_x + 2, text_y))
                text_y += 16

            stripe_y = card_rect.height - 7 + int(math.sin(time.time() * 8) * 2)
            pygame.draw.line(card, self.alert_color, (16, stripe_y), (card_rect.width - 16, stripe_y), 2)
            card.set_alpha(min(255, max(242, alpha + 18)))
            self.screen.blit(card, card_rect.topleft)

    def draw_start_briefing_overlay(self):
        if self.start_briefing_timer <= 0:
            return
        progress = 1.0 - min(1.0, self.start_briefing_timer / 3.0)
        alpha = int(230 * (1.0 - progress * 0.35))
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((8, 12, 22, 150))
        self.screen.blit(overlay, (0, 0))

        panel = pygame.Rect(0, 0, 500, 168)
        panel.center = (WIDTH // 2, 160)
        card = pygame.Surface(panel.size, pygame.SRCALPHA)
        pygame.draw.rect(card, (12, 18, 30, 248), card.get_rect(), border_radius=18)
        pygame.draw.rect(card, (130, 160, 200), card.get_rect(), 2, border_radius=18)
        title = self.font_medium.render("임무 브리핑", True, (245, 245, 255))
        card.blit(title, title.get_rect(center=(panel.width // 2, 30)))
        lines = [
            "목표를 먼저 확인하세요.",
            "TAB으로 포커스를 전환하고 1~7로 대응합니다.",
            "E는 대피 모드, B는 상점, H는 UI 숨김입니다.",
        ]
        for idx, line in enumerate(lines):
            surf = self.font_small.render(line, True, (215, 226, 242))
            card.blit(surf, surf.get_rect(center=(panel.width // 2, 72 + idx * 28)))
        tip = self.font_tiny.render("브리핑은 3초 후 사라집니다.", True, (180, 194, 220))
        card.blit(tip, tip.get_rect(center=(panel.width // 2, 146)))
        card.set_alpha(max(0, min(255, alpha)))
        self.screen.blit(card, panel.topleft)

    ###########################################################
    # 상태 업데이트
    ###########################################################

    def update_play_state(self, dt: float):
        # Update accumulated time (pause-aware)
        if not self.paused:
            self.accumulated_time += dt
        else:
            self.pause_accumulated_time += dt
        
        elapsed = self.accumulated_time
        remaining_time = max(0.0, self.total_time_limit - elapsed)

        # UI 애니메이션
        if self.ui_animating:
            self.ui_animation_progress = min(1.0, self.ui_animation_progress + dt * 2.0)
            if self.ui_animation_progress >= 1.0:
                self.ui_animating = False

        if self.start_briefing_timer > 0:
            self.start_briefing_timer = max(0.0, self.start_briefing_timer - dt)
        if self.tutorial_hint_timer > 0:
            self.tutorial_hint_timer = max(0.0, self.tutorial_hint_timer - dt)

        if self.evac_mode_active:
            self.update_evac_player(dt)

        if remaining_time <= 0:
            self.score = self.calculate_final_score()
            self.end_run("시간이 다 되어 종료되었습니다.")
            return

        # 재난 스폰 (동시에 여러 개 가능)
        if elapsed >= self.next_event_game_time:
            self.spawn_disaster()
            interval = max(2.5, 8.0 / self.get_difficulty_factor())
            self.next_event_game_time = elapsed + interval

        # 각 재난의 시간 경과 / 확산 / 시간 초과 처리
        for inst in list(self.active_disasters):
            if inst.resolved:
                self.active_disasters.remove(inst)
                continue

            # 확산형 재난(홍수/산불/지진)은 반경이 시간에 따라 증가
            if inst.disaster.type_id in ("flood", "wildfire", "earthquake"):
                inst.radius += inst.spread_speed * dt
                
                # 최적화: 반경 안의 시민에게 피해 (한 번만 순회)
                for c in self.citizens_visual:
                    if not c.alive or c.state == "RESCUED":
                        continue
                    dist = (c.pos - inst.position).length()
                    if dist < inst.radius:
                        # 구역별 취약도 적용
                        vulnerability_multiplier = 1.0
                        for b in self.buildings:
                            if b.rect.collidepoint(c.pos):
                                vulnerability_multiplier = b.vulnerability.get(inst.disaster.type_id, 1.0)
                                break
                        
                        # 일정 확률로 부상/사망 (취약도에 따라 조정)
                        if random.random() < 0.02 * dt * self.get_difficulty_factor() * vulnerability_multiplier:
                            # 시민 사망
                            c.alive = False
                            self.citizens = max(0, self.citizens - 1)
                            self.total_deaths += 1
                            self.score -= 15  # 사망 점수
                        
                        # 지진 시 건물 피해와 부상 처리도 같이 함
                        if inst.disaster.type_id == "earthquake" and dist < inst.radius * 0.7:
                            c.state = "INJURED"
                
                # 지진 시 건물 피해 (별도로 처리)
                if inst.disaster.type_id == "earthquake":
                    for b in self.buildings:
                        if not b.collapsed and (pygame.Vector2(b.rect.center) - inst.position).length() < inst.radius:
                            # 구역별 취약도 적용
                            vulnerability_multiplier = b.vulnerability.get(inst.disaster.type_id, 1.0)
                            if random.random() < 0.01 * dt * vulnerability_multiplier:
                                b.collapsed = True
                                self.score -= 5  # 건물 파괴
                    
                    # 지진이 확산되면 연쇄 재난 시도
                    if inst.radius > 40 and not inst.is_chain_disaster:
                        self.try_spawn_chain_disaster(inst, dt)

            # 의사결정 제한 시간
            if time.time() - inst.decision_start_time >= self.disaster_decision_time_limit:
                self.apply_disaster_outcome(inst, "no_action")
                self.active_disasters.remove(inst)

        # 헬기
        if self.helicopter:
            self.helicopter.update(dt)
            if self.helicopter.is_finished():
                self.helicopter = None

        # 시민/구조대 업데이트
        for c in self.citizens_visual:
            c.update(dt, self)
            if c.alive and c.state == "RESCUED" and not c.rescored:
                c.rescored = True
                self.rescued_citizens += 1
                self.total_rescues += 1
                self.score += 5
        for team in self.rescue_teams:
            team.update(dt, self)

        # 눈 파티클 업데이트 (눈보라 시)
        if self.is_blizzard_active():
            self.update_snow_particles(dt)
        
        # 자원 재생
        self.update_resources(dt)

        # 지진 화면 흔들림 감쇠
        if self.shake_intensity > 0:
            self.shake_timer += dt
            decay = 1.0 - min(1.0, self.shake_timer / self.shake_duration)
            self.shake_intensity = 12.0 * max(0.0, decay)
            if self.shake_intensity < 0.5:
                self.shake_intensity = 0.0

        # 명령 쿨다운 감소
        for k, v in self.command_timers.items():
            if v > 0:
                self.command_timers[k] = max(0.0, v - dt)

        if self.command_points < self.max_command_points:
            self.command_points = min(self.max_command_points, self.command_points + dt * self.command_regen_rate)

        if self.combo_timer > 0:
            self.combo_timer = max(0.0, self.combo_timer - dt)
            if self.combo_timer <= 0:
                self.combo_count = 0

        # 경고 플래시/알림 감소
        if self.flash_timer > 0:
            self.flash_timer -= dt
        if self.alert_timer > 0:
            self.alert_timer -= dt

        # 시민 절반 이상 사망 시 게임 종료
        if self.total_deaths >= self.initial_citizens // 2:
            self.end_run("사망자가 너무 많아 패배했습니다.")

    def handle_play_events(self, events):
        for event in events:
            if event.type == pygame.KEYDOWN:
                self.unlock_audio()
                if self.shop_open:
                    if event.key in (pygame.K_b, pygame.K_ESCAPE):
                        self.toggle_shop()
                    continue
                if event.key == pygame.K_m:
                    if self.music_paused:
                        self.resume_bgm()
                    else:
                        self.pause_bgm()
                    continue
                if event.key in (pygame.K_LEFTBRACKET, pygame.K_MINUS):
                    self.set_bgm_volume(self.music_volume - 0.05)
                    self.add_popup(f"BGM 볼륨 {int(self.music_volume * 100)}%", (180, 220, 255), 1.2)
                    continue
                if event.key in (pygame.K_RIGHTBRACKET, pygame.K_EQUALS):
                    self.set_bgm_volume(self.music_volume + 0.05)
                    self.add_popup(f"BGM 볼륨 {int(self.music_volume * 100)}%", (180, 220, 255), 1.2)
                    continue
                if event.key == pygame.K_e:
                    self.toggle_evac_mode()
                    continue
                if event.key == pygame.K_h:
                    self.toggle_ui_hidden()
                    continue
                if self.evac_mode_active and event.key not in (pygame.K_p, pygame.K_ESCAPE):
                    continue
                if event.key in (pygame.K_p, pygame.K_ESCAPE):
                    self.toggle_pause()
                    continue
                if event.key == pygame.K_b:
                    self.toggle_shop()
                    continue
                if self.paused:
                    continue
                if event.key == pygame.K_TAB:
                    self.cycle_focus(1)
                    continue
                action_key = self.action_shortcuts.get(event.key)
                if action_key:
                    self.trigger_action(action_key)
                    continue

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                mx, my = event.pos
                if not self.paused and not self.shop_open and not self.evac_mode_active and mx < WIDTH - 280 and my < HEIGHT - 152:
                    self.map_dragging = True
                    self.map_drag_last = pygame.Vector2(mx, my)
                continue

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.unlock_audio()
                if self.button_ui_toggle.is_clicked(event):
                    self.toggle_ui_hidden()
                    continue
                if self.evac_mode_active:
                    continue
                if self.ui_hidden:
                    continue
                if self.shop_open:
                    if self.button_shop.is_clicked(event):
                        self.toggle_shop()
                        continue
                    clicked_shop_item = False
                    for btn in self.shop_buttons:
                        if btn.is_clicked(event):
                            clicked_shop_item = True
                            if btn.command_key == "SHOP_CLOSE":
                                self.close_shop()
                            elif btn.command_key == "SHOP_MANPOWER":
                                self.buy_shop_upgrade("manpower")
                            elif btn.command_key == "SHOP_BUDGET":
                                self.buy_shop_upgrade("budget")
                            elif btn.command_key == "SHOP_MATERIALS":
                                self.buy_shop_upgrade("materials")
                            elif btn.command_key == "SHOP_COMMAND":
                                self.buy_shop_upgrade("command")
                            break
                    if clicked_shop_item:
                        continue
                    # 상점 외부 클릭은 무시
                    continue
                if self.button_shop.is_clicked(event):
                    self.toggle_shop()
                    continue
                if self.paused:
                    continue
                mx, my = event.pos
                # 맵 영역 클릭 시 구역 선택
                if mx < WIDTH - 280 and my < HEIGHT - 152:
                    self.selected_district = None
                    world_pos = pygame.Vector2(mx - self.camera_offset.x, my - self.camera_offset.y)
                    for b in self.buildings:
                        if b.rect.collidepoint(world_pos):
                            self.selected_district = b
                            break
                else:
                    action = None
                    if self.button_evac.is_clicked(event):
                        action = "대피령"
                    elif self.button_rescue.is_clicked(event):
                        action = "구조대 파견"
                    elif self.button_fire.is_clicked(event):
                        action = "소방대 투입"
                    elif self.button_medical.is_clicked(event):
                        action = "의료 지원"
                    elif self.button_heli.is_clicked(event):
                        action = "헬기 구조"
                    elif self.button_police.is_clicked(event):
                        action = "경찰 통제"
                    elif self.button_watch.is_clicked(event):
                        action = "관찰 모드"

                    if action:
                        self.trigger_action(action)
            if event.type == pygame.MOUSEBUTTONUP and event.button == 3:
                self.map_dragging = False
                self.map_drag_last = None
            if event.type == pygame.MOUSEMOTION and self.map_dragging and not self.paused and not self.shop_open and not self.evac_mode_active:
                self.camera_offset += pygame.Vector2(event.rel)
                self.clamp_camera_offset()

    ###########################################################
    # 화면 렌더링
    ###########################################################

    def render_menu(self):
        # Use cached background to prevent repeated expensive scaling
        if not hasattr(self, 'cached_menu_bg') or self.cached_menu_bg is None:
            self.cached_menu_bg = pygame.transform.smoothscale(self.city_surface, (WIDTH, HEIGHT))
        bg = self.cached_menu_bg
        self.screen.blit(bg, (0, 0))

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((6, 10, 20, 160))
        self.screen.blit(overlay, (0, 0))

        panel_rect = pygame.Rect(0, 0, 760, 560)
        panel_rect.center = (WIDTH // 2, HEIGHT // 2)
        panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel, (14, 22, 36, 228), panel.get_rect(), border_radius=28)
        pygame.draw.rect(panel, (120, 150, 190), panel.get_rect(), 2, border_radius=28)

        hero_rect = pygame.Rect(24, 24, panel_rect.width - 48, 150)
        pygame.draw.rect(panel, (22, 36, 58, 255), hero_rect, border_radius=22)
        pygame.draw.rect(panel, (86, 130, 190), hero_rect, 1, border_radius=22)

        tag = self.font_tiny.render("CITY CRISIS SIMULATION", True, (140, 190, 255))
        panel.blit(tag, (44, 36))
        title_shadow = self.font_large.render("Disaster Commander", True, (20, 28, 44))
        panel.blit(title_shadow, (46, 45))
        title = self.font_large.render("Disaster Commander", True, (242, 245, 255))
        panel.blit(title, (44, 43))
        subtitle_lines = self.wrap_text("도시 전체를 지휘해 재난을 막아내세요", self.font_menu_subtitle, hero_rect.width - 40)
        for idx, line in enumerate(subtitle_lines):
            subtitle = self.font_menu_subtitle.render(line, True, (208, 220, 238))
            panel.blit(subtitle, (46, 104 + idx * 18))
        minor_lines = self.wrap_text("재난 대응 시뮬레이션 | 빠른 판단 | 구조 최우선", self.font_menu_meta, hero_rect.width - 40)
        minor_y = 132 + max(0, len(subtitle_lines) - 1) * 18
        for idx, line in enumerate(minor_lines):
            minor = self.font_menu_meta.render(line, True, (170, 194, 226))
            panel.blit(minor, (46, minor_y + idx * 16))

        info_rect = pygame.Rect(24, 190, 462, 176)
        pygame.draw.rect(panel, (18, 28, 44, 245), info_rect, border_radius=20)
        pygame.draw.rect(panel, (72, 96, 126), info_rect, 1, border_radius=20)
        info_title = self.font_small.render("작전 개요", True, (236, 240, 255))
        panel.blit(info_title, (42, 206))
        lines = [
            "당신은 재난 대응 책임자입니다.",
            "30초 튜토리얼: 목표와 현재 모드를 먼저 확인하세요.",
            "TAB으로 포커스를 옮기고 1~7로 즉시 대응하세요.",
            "E는 대피 모드, B는 상점, H는 UI 숨김입니다.",
        ]
        text_y = 228
        for line in lines:
            wrapped = self.wrap_text(line, self.font_menu_subtitle, info_rect.width - 60)
            pygame.draw.circle(panel, (110, 190, 255), (48, text_y + 10), 4)
            for j, part in enumerate(wrapped):
                text = self.font_menu_subtitle.render(part, True, (214, 224, 242))
                panel.blit(text, (64, text_y + j * 20))
            text_y += max(30, len(wrapped) * 20 + 8)

        side_rect = pygame.Rect(504, 190, 232, 176)
        pygame.draw.rect(panel, (18, 28, 44, 245), side_rect, border_radius=20)
        pygame.draw.rect(panel, (72, 96, 126), side_rect, 1, border_radius=20)
        side_title = self.font_small.render("오늘의 목표", True, (236, 240, 255))
        panel.blit(side_title, (522, 206))
        rescue_target, death_limit, _, _ = self.get_current_objective_status()
        diff_label = self.difficulty_names.get(self.difficulty, self.difficulty)
        hs = self.high_scores.get(self.difficulty, 0)
        
        # 난이도별 시간 표시
        time_text = ""
        if self.difficulty == "Easy":
            time_text = "제한 시간  6분 30초"
        elif self.difficulty == "Hard":
            time_text = "제한 시간  1분 30초"
        else:
            time_text = "제한 시간  3분 30초"
        
        side_lines = [
            f"난이도  {diff_label}",
            time_text,
            f"구조 목표  {rescue_target}",
            f"사망 제한  {death_limit}",
            f"최고 점수  {hs:,}",
        ]
        for idx, line in enumerate(side_lines):
            surf = self.font_menu_subtitle.render(line, True, (220, 230, 245))
            panel.blit(surf, (522, 238 + idx * 28))

        diff_pill = pygame.Rect(0, 0, 244, 54)
        diff_pill.center = (panel_rect.width // 2, 448)
        pygame.draw.rect(panel, (33, 56, 88, 250), diff_pill, border_radius=18)
        pygame.draw.rect(panel, (92, 132, 188), diff_pill, 1, border_radius=18)
        pill_label = self.font_tiny.render("작전 난이도", True, (155, 194, 245))
        panel.blit(pill_label, pill_label.get_rect(center=(diff_pill.centerx, diff_pill.y + 15)))
        pill_value = self.font_medium.render(diff_label, True, (242, 245, 255))
        panel.blit(pill_value, pill_value.get_rect(center=(diff_pill.centerx, diff_pill.y + 37)))

        self.screen.blit(panel, panel_rect.topleft)

        self.diff_left_button.draw(self.screen, panel_rect.x + diff_pill.x - 58, panel_rect.y + diff_pill.y + 4)
        self.diff_right_button.draw(self.screen, panel_rect.x + diff_pill.right + 12, panel_rect.y + diff_pill.y + 4)

        btn = self.menu_buttons[0]
        btn.draw(self.screen, panel_rect.centerx - btn.rect.width // 2, panel_rect.bottom - btn.rect.height - 18)

    def render_play(self):
        # 배경 (지진 흔들림 반영)
        if any(d.disaster.type_id == "earthquake" for d in self.active_disasters):
            self.draw_earthquake_background()
        else:
            self.screen.fill((32, 54, 80))
            self.screen.blit(self.city_surface, self.camera_offset)

        # 건물
        self.draw_buildings()

        # 시민 / 구조대
        self.draw_citizens()
        self.draw_evac_player()
        for team in self.rescue_teams:
            team.draw(self.screen, self.camera_offset)

        # HUD
        elapsed = self.accumulated_time
        remaining_time = max(0.0, self.total_time_limit - elapsed)
        self.draw_main_hud(remaining_time)

        # 재난 연출
        self.draw_disaster_effects()

        # 눈 파티클 (눈보라 시)
        if self.is_blizzard_active():
            self.draw_snow_particles(self.screen)

        # 헬기
        self.draw_helicopter()

        # UI 토글 버튼은 항상 남겨둔다.
        self.button_ui_toggle.text = "UI 보기" if self.ui_hidden else "UI 숨김"
        self.button_ui_toggle.draw(self.screen)

        if self.start_briefing_timer > 0:
            self.draw_start_briefing_overlay()

        if not self.ui_hidden:
            # 팝업
            self.draw_popups()

            # 붉은 플래시 + 중앙 경고 텍스트
            self.draw_flash_and_alert()
        if self.shop_open:
            self.draw_shop_overlay()
        elif self.paused:
            self.draw_pause_overlay()

    def render_game_over(self):
        self.screen.fill((15, 10, 26))

        final_score = getattr(self, "last_final_score", self.calculate_final_score())
        grade = getattr(self, "last_grade", self.grade_from_score(final_score))
        record = getattr(self, "last_record", False)
        end_reason = getattr(self, "last_end_reason", "")

        title_text = "패배" if end_reason else "결과"
        title_color = (255, 170, 170) if end_reason else (240, 240, 255)
        title = self.font_large.render(title_text, True, title_color)
        self.screen.blit(title, title.get_rect(center=(WIDTH // 2, 90)))

        if end_reason:
            reason = self.font_medium.render(end_reason, True, (255, 210, 210))
            self.screen.blit(reason, reason.get_rect(center=(WIDTH // 2, 132)))

        elapsed_total = int(getattr(self, "last_elapsed_time", min(self.total_time_limit, self.accumulated_time)))
        minutes = elapsed_total // 60
        seconds = elapsed_total % 60

        diff_label = self.difficulty_names.get(self.difficulty, self.difficulty)

        stats = [
            f"난이도: {diff_label}",
            f"최종 점수: {final_score:,}",
            f"보유 코인: {self.coins}",
            f"총 획득 코인: {self.total_coins_earned}",
            f"대피 성공: {self.evac_mode_successes}",
            f"생존 시민 수: {self.citizens}",
            f"총 구조 인원: {self.total_rescues}",
            f"총 사망자 수: {self.total_deaths}",
            f"발생한 재난 수: {self.events_handled}",
            f"플레이 시간: {minutes:02d}:{seconds:02d}",
        ]

        # 왼쪽에 스탯 정보, 오른쪽에 바 차트 - 간격 조정
        left_x = WIDTH // 2 - 350
        right_x = WIDTH // 2 + 60
        y = 164 if end_reason else 146
        for s in stats:
            surf = self.font_small.render(s, True, (225, 225, 240))
            self.screen.blit(surf, (left_x, y))
            y += 24

        # 등급 표시
        grade_color = {
            "S": (255, 215, 0),
            "A": (144, 238, 144),
            "B": (135, 206, 250),
            "C": (255, 160, 122),
        }.get(grade, (255, 255, 255))
        grade_text = f"등급: {grade}"
        grade_surf = self.font_large.render(grade_text, True, grade_color)
        self.screen.blit(grade_surf, grade_surf.get_rect(center=(right_x + 100, 220 if not end_reason else 236)))

        if record:
            record_surf = self.font_medium.render("신기록 달성!", True, (255, 220, 120))
            self.screen.blit(record_surf, record_surf.get_rect(center=(right_x + 100, 270 if not end_reason else 286)))

        # 간단한 바 차트 (오른쪽) - 위치 조정
        chart_base_y = 320 if not end_reason else 344
        chart_x = right_x
        bar_width = 100
        max_val = max(1, self.citizens, self.total_rescues, self.total_deaths)
        max_height = 150
        scale = max_height / max_val
        items = [
            ("생존", self.citizens, (100, 220, 120)),
            ("구조", self.total_rescues, (120, 180, 250)),
            ("사망", self.total_deaths, (230, 80, 80)),
        ]
        for i, (label, value, color) in enumerate(items):
            h = int(value * scale)
            bar = pygame.Rect(chart_x + i * (bar_width + 30), chart_base_y + (max_height - h), bar_width, h)
            pygame.draw.rect(self.screen, color, bar)
            pygame.draw.rect(self.screen, (0, 0, 0), bar, 2)
            lb = self.font_tiny.render(label, True, (235, 235, 245))
            self.screen.blit(lb, lb.get_rect(center=(bar.centerx, chart_base_y + max_height + 12)))
            val = self.font_tiny.render(str(value), True, (235, 235, 245))
            self.screen.blit(val, val.get_rect(center=(bar.centerx, bar.top - 12)))

        # 결과 버튼은 중앙 하단에 배치
        retry_x = WIDTH // 2 - 180
        quit_x = WIDTH // 2 + 20
        retry_y = 540 if not end_reason else 554
        quit_y = retry_y
        self.result_buttons[0].rect.topleft = (retry_x, retry_y)
        self.result_buttons[1].rect.topleft = (quit_x, quit_y)
        for btn in self.result_buttons:
            btn.draw(self.screen)

        rescue_target, death_limit, rescue_ok, death_ok = self.get_current_objective_status()
        mission = "작전 성공" if rescue_ok and death_ok else "작전 미달"
        mission_color = (180, 255, 180) if rescue_ok and death_ok else (255, 180, 160)
        mission_title = self.font_small.render(mission, True, mission_color)
        mission_detail = self.font_tiny.render(
            f"구조 목표 {rescue_target}  |  사망 제한 {death_limit}",
            True,
            (220, 220, 235),
        )
        self.screen.blit(mission_title, mission_title.get_rect(center=(WIDTH // 2 - 70, HEIGHT - 222)))
        self.screen.blit(mission_detail, mission_detail.get_rect(center=(WIDTH // 2 - 70, HEIGHT - 198)))

    ###########################################################
    # Main loop
    ###########################################################

    def init_snow_particles(self):
        """Initialize snow particles."""
        num_particles = random.randint(150, 200)
        self.snow_particles = []
        for _ in range(num_particles):
            self.snow_particles.append({
                'x': random.randint(0, WIDTH - 260),
                'y': random.randint(-HEIGHT, HEIGHT),
                'speed': random.uniform(20, 60),
                'size': random.randint(1, 2)
            })

    def update_snow_particles(self, dt: float):
        """Update snow particles."""
        for p in self.snow_particles:
            p['y'] += p['speed'] * dt
            if p['y'] > HEIGHT:
                p['y'] = random.randint(-50, -10)
                p['x'] = random.randint(0, WIDTH - 260)

    def draw_snow_particles(self, surface):
        """Draw snow particles."""
        for p in self.snow_particles:
            pygame.draw.circle(surface, (240, 240, 255), (int(p['x']), int(p['y'])), p['size'])

    def run(self):
        running = True
        while running:
            dt = self.clock.tick(FPS) / 1000.0
            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                    self.unlock_audio()
                    self.toggle_fullscreen()
                elif event.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                    self.unlock_audio()

            self.update_bgm_state(dt)

            if self.state == STATE_MENU:
                for event in events:
                    if self.menu_buttons[0].is_clicked(event):
                        self.play_click_sound()
                        self.reset_game_state()
                        self.state = STATE_PLAYING
                    elif len(self.menu_buttons) > 1 and self.menu_buttons[1].is_clicked(event):
                        self.play_click_sound()
                        self.toggle_fullscreen()
                    elif self.diff_left_button.is_clicked(event):
                        self.play_click_sound()
                        self.change_difficulty(-1)
                    elif self.diff_right_button.is_clicked(event):
                        self.play_click_sound()
                        self.change_difficulty(1)
                self.render_menu()

            elif self.state == STATE_PLAYING:
                self.handle_play_events(events)
                if not self.paused and self.state == STATE_PLAYING:
                    self.update_play_state(dt)
                if self.state == STATE_GAME_OVER:
                    self.render_game_over()
                else:
                    self.render_play()

            elif self.state == STATE_GAME_OVER:
                for event in events:
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        if self.result_buttons[0].is_clicked(event):
                            self.play_click_sound()
                            self.reset_game_state()
                            self.state = STATE_PLAYING
                        elif self.result_buttons[1].is_clicked(event):
                            self.play_click_sound()
                            running = False
                self.render_game_over()

            pygame.display.flip()

        if self.music_available:
            if self.bgm_channel is not None:
                self.bgm_channel.fadeout(250)
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    Game().run()
