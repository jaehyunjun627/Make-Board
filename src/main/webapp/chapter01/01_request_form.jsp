<%@ page language="java" contentType="text/html; charset=UTF-8"
    pageEncoding="UTF-8"%>
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>Request Form</title>
<link rel="stylesheet" href="../css/style01.css" />
</head>
<body>

<div>
<h2>회원 정보 입력</h2>
<hr />

<form action="request_result.jsp" method="get">
<table width="400" border="1" cellspacing="0" cellpadding="5">

<!-- 이름 -->
<tr>
    <td width="100">이름</td>
    <td>
        <input type="text" size="10" name="username" />
    </td>
</tr>

<!-- 직업 -->
<tr>
    <td>직업</td>
    <td>
        <select name="job">
            <option value="무직" selected>무직</option>
            <option value="회사원">회사원</option>
            <option value="전문직">전문직</option>
            <option value="학생">학생</option>
        </select>
    </td>
</tr>

<!-- 관심분야 -->
<tr>
    <td>관심분야</td>
    <td>
        <label><input type="checkbox" name="favorite" value="스포츠"> 스포츠</label>
        <label><input type="checkbox" name="favorite" value="IT"> IT</label>
        <label><input type="checkbox" name="favorite" value="과학"> 과학</label>
    </td>
</tr>

<!-- 버튼 -->
<tr>
    <td colspan="2" align="center">
        <input type="submit" value="확인">
        <input type="reset" value="취소">
    </td>
</tr>

</table>
</form>

</div>

</body>
</html>