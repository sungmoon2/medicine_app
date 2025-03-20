-- 데이터베이스 생성
CREATE DATABASE IF NOT EXISTS medicine_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 데이터베이스 선택
USE medicine_db;

-- 사용자 테이블 생성
CREATE TABLE IF NOT EXISTS users ( 
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    age INT NOT NULL,
    ssn VARCHAR(8) NOT NULL,  -- 주민등록번호 (앞 6자리-뒷자리 첫번째자리)
    phone VARCHAR(15) NOT NULL,  -- 휴대전화번호
    height DECIMAL(5,2),  -- 키 (cm)
    weight DECIMAL(5,2),  -- 몸무게 (kg)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 의약품 정보 테이블 (추후 개발을 위한 예시)
CREATE TABLE IF NOT EXISTS medicines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    ingredient TEXT,
    effect TEXT,
    usage_info TEXT,
    caution TEXT,
    company VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 사용자 의약품 관리 테이블 (추후 개발을 위한 예시)
CREATE TABLE IF NOT EXISTS user_medicines (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    medicine_id INT NOT NULL,
    dosage VARCHAR(100),
    start_date DATE,
    end_date DATE,
    reminder BOOLEAN DEFAULT FALSE,
    reminder_time TIME,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (medicine_id) REFERENCES medicines(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
