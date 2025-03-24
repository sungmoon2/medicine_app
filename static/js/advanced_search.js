/**
 * 의약품 고급 검색 자바스크립트
 */
document.addEventListener('DOMContentLoaded', function() {
    // 모양 선택 관련 기능
    initShapeSelection();
    
    // 색상 선택 관련 기능
    initColorSelection();
    
    // 제조사 드롭다운 연동
    initManufacturerSelect();
    
    // 폼 제출 전 처리
    initFormSubmission();
    
    // 폼 초기화 이벤트
    initFormReset();
});

/**
 * 모양 선택 기능 초기화
 */
function initShapeSelection() {
    const shapeItems = document.querySelectorAll('.shape-item');
    const drugShapeInput = document.getElementById('drug_shape');
    const selectedShapeImg = document.getElementById('selectedShapeImg');
    const selectShapeBtn = document.getElementById('selectShapeBtn');
    
    let selectedShape = '';
    
    // URL 파라미터에서 선택된 모양 확인
    const urlParams = new URLSearchParams(window.location.search);
    const shapeFromUrl = urlParams.get('drug_shape');
    
    // 모양 아이템 클릭 이벤트
    shapeItems.forEach(item => {
        const shape = item.getAttribute('data-shape');
        
        // URL에서 가져온 모양과 일치하는 아이템 활성화
        if (shapeFromUrl && shape === shapeFromUrl) {
            item.classList.add('active');
            selectedShape = shape;
            
            // 이미지 업데이트
            const imgSrc = item.querySelector('img').src;
            if (selectedShapeImg) {
                selectedShapeImg.src = imgSrc;
                selectedShapeImg.alt = shape;
            }
            
            // 숨겨진 입력 필드 업데이트
            if (drugShapeInput) {
                drugShapeInput.value = shape;
            }
        }
        
        // 클릭 이벤트
        item.addEventListener('click', function() {
            // 이전 선택 제거
            shapeItems.forEach(el => el.classList.remove('active'));
            
            // 현재 선택 표시
            this.classList.add('active');
            
            // 선택한 모양 저장
            selectedShape = this.getAttribute('data-shape');
        });
    });
    
    // 모양 선택 버튼 클릭 이벤트
    if (selectShapeBtn) {
        selectShapeBtn.addEventListener('click', function() {
            if (selectedShape) {
                // 선택한 모양 값 설정
                if (drugShapeInput) {
                    drugShapeInput.value = selectedShape;
                }
                
                // 선택한 모양 이미지 표시
                const selectedItem = document.querySelector(`.shape-item[data-shape="${selectedShape}"]`);
                if (selectedItem && selectedShapeImg) {
                    const imgSrc = selectedItem.querySelector('img').src;
                    selectedShapeImg.src = imgSrc;
                    selectedShapeImg.alt = selectedShape;
                }
            }
        });
    }
}

/**
 * 색상 선택 기능 초기화
 */
function initColorSelection() {
    const colorCheckboxes = document.querySelectorAll('.color-checkbox');
    
    // URL 파라미터에서 선택된 색상 확인
    const urlParams = new URLSearchParams(window.location.search);
    const colorsFromUrl = urlParams.getAll('color');
    
    // 색상 체크박스 초기화
    colorCheckboxes.forEach(checkbox => {
        const color = checkbox.value;
        
        // URL에서 가져온 색상과 일치하는 체크박스 체크
        if (colorsFromUrl.includes(color)) {
            checkbox.checked = true;
        }
        
        // 클릭 이벤트
        checkbox.addEventListener('change', function() {
            // 색상 박스 스타일 업데이트 (필요하면)
        });
    });
}

/**
 * 제조사 드롭다운 연동 기능 초기화
 */
function initManufacturerSelect() {
    const entpNameInput = document.getElementById('entp_name');
    const entpNameSelect = document.getElementById('entp_name_select');
    
    if (entpNameInput && entpNameSelect) {
        // URL 파라미터에서 제조사 확인
        const urlParams = new URLSearchParams(window.location.search);
        const entp = urlParams.get('entp_name');
        
        // 제조사 입력 필드 초기화
        if (entp) {
            entpNameInput.value = entp;
            
            // 드롭다운에서 일치하는 값 찾기
            for (let i = 0; i < entpNameSelect.options.length; i++) {
                if (entpNameSelect.options[i].value === entp) {
                    entpNameSelect.selectedIndex = i;
                    break;
                }
            }
        }
        
        // 드롭다운 변경 이벤트
        entpNameSelect.addEventListener('change', function() {
            if (this.value) {
                entpNameInput.value = this.value;
            }
        });
    }
}

/**
 * 폼 제출 전 처리 초기화
 */
function initFormSubmission() {
    const searchForm = document.getElementById('advancedSearchForm');
    
    if (searchForm) {
        searchForm.addEventListener('submit', function(e) {
            // 빈 파라미터 제거
            const formData = new FormData(this);
            for (const [key, value] of formData.entries()) {
                if (!value || value.trim() === '') {
                    const inputs = this.querySelectorAll(`[name="${key}"]`);
                    inputs.forEach(input => {
                        if (input.type === 'text' || input.type === 'select-one') {
                            input.disabled = true;
                        }
                    });
                }
            }
        });
    }
}

/**
 * 폼 초기화 이벤트 초기화
 */
function initFormReset() {
    const resetButton = document.querySelector('button[type="reset"]');
    
    if (resetButton) {
        resetButton.addEventListener('click', function() {
            // 색상 선택 초기화
            document.querySelectorAll('.color-checkbox').forEach(checkbox => {
                checkbox.checked = false;
            });
            
            // 모양 선택 초기화
            const selectedShapeImg = document.getElementById('selectedShapeImg');
            const drugShapeInput = document.getElementById('drug_shape');
            
            if (selectedShapeImg) {
                selectedShapeImg.src = '/static/img/shapes/circle.png';
                selectedShapeImg.alt = '원형';
            }
            
            if (drugShapeInput) {
                drugShapeInput.value = '';
            }
            
            // 선택된 모양 클래스 초기화
            document.querySelectorAll('.shape-item').forEach(el => {
                el.classList.remove('active');
            });
            
            // 제조사 드롭다운 초기화
            const entpNameSelect = document.getElementById('entp_name_select');
            if (entpNameSelect) {
                entpNameSelect.selectedIndex = 0;
            }
        });
    }
}